"""The edge export boundary, S13 / D19 (R09, E0-8, design 5.12, 7.8).

R09, as interpreted and approved at E0-8:

    **No occupancy, presence or person-level field is ever transmitted.**  That
    alone doesn't make exports safe, because aggregate energy profiles are known
    to reveal presence and routines.  Baile Nua can measure this residual risk
    directly, because it has ground truth.

So this module does two separate things and keeps them apart:

1. It **builds** the export - and the allow-list is positive, not negative:
   only the fields design 6.1 lists for D19 are assembled, so a new field
   cannot arrive by being forgotten about.  The schema's
   ``forbidden_field_patterns`` then refuse it a second time on the write path,
   and the leakage test refuses it a third time in CI.  Three independent
   refusals, because R09 is the one requirement where a silent failure is worst.
2. It **does not** assess the privacy risk.  Design 7.8's inference-risk test is
   a week-3 deliverable, and :func:`export_configurations` builds all four
   configurations U20 asks for so that the test has something to run on, without
   claiming any of them is safe.  :data:`CLAIM_BOUNDARY` is attached to every
   export so no later reader mistakes "contains no occupancy field" for
   "occupancy cannot be inferred".
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.schema import load
from baile_nua.rng import stable_entity_id
from baile_nua.schema.access import audit_frame

__all__ = [
    "D19_FIELDS",
    "EXPORT_CONFIGS",
    "CLAIM_BOUNDARY",
    "build_export",
    "export_configurations",
    "ExportConfig",
]

#: The ONLY fields an edge export may contain.  A positive allow-list, taken
#: from the schema itself so the two cannot drift apart.
D19_FIELDS: tuple[str, ...] = tuple(load()["D19"].field_map)

CLAIM_BOUNDARY = (
    "This export contains no occupancy, presence or person-level field (R09, "
    "E0-8). That is a statement about what is TRANSMITTED, not about what can "
    "be INFERRED: aggregate energy profiles are known to reveal presence and "
    "routines, and design 7.8's inference-risk test - which measures it against "
    "Baile Nua's own ground truth - is a week-3 deliverable and has NOT been "
    "run. No privacy claim is made here."
)


@dataclasses.dataclass(frozen=True)
class ExportConfig:
    """One of the four configurations U20 compares (design 7.8)."""

    name: str
    interval_min: int
    aggregate_over: str          # "premises" | "estate"
    include_profile: bool
    include_compliance: bool
    noise_scale_wh: float = 0.0
    note: str = ""


#: All four, built so the 7.8 test has something to compare.  U20's decision -
#: which to use - is explicitly deferred to after that test (design 7.8: "The
#: trade-off is a decision (U20)"), so none is marked as the default here.
EXPORT_CONFIGS: dict[str, ExportConfig] = {
    "home_30min": ExportConfig(
        "home_30min", 30, "premises", True, True,
        note="Best for settlement, worst for privacy (design 7.8).",
    ),
    "home_15min": ExportConfig(
        "home_15min", 15, "premises", True, True,
        note="Finer interval; more settlement value and more inference risk.",
    ),
    "estate_aggregate": ExportConfig(
        "estate_aggregate", 30, "estate", True, True,
        note="EdgeWare-style aggregation; individual routines are mixed.",
    ),
    "compliance_only": ExportConfig(
        "compliance_only", 30, "premises", False, True,
        note="Only flexibility compliance leaves the home; least settlement "
             "value, least inference risk.",
    ),
}


def build_export(
    *,
    premises_id: str,
    minute_index: pd.DatetimeIndex,
    net_import_w: np.ndarray,
    net_export_w: np.ndarray,
    config: ExportConfig,
    flex_event_id: str | None = None,
    flex_compliance_pct: float | None = None,
    quality: str = "ok",
    estate_id: str | None = None,
) -> pd.DataFrame:
    """Assemble one premises' (or estate's) export for a period.

    Everything is derived from the net meter series alone.  That is not a
    convenience - it is the mechanism by which R09 holds: the function has no
    access to occupancy, activities or persons, so it could not transmit them
    even if a later edit asked it to.
    """
    if len(net_import_w) != len(minute_index) or len(net_export_w) != len(minute_index):
        raise ValueError("net power arrays must match the minute index length")

    frame = pd.DataFrame(
        {"import_w": np.asarray(net_import_w, dtype=np.float64),
         "export_w": np.asarray(net_export_w, dtype=np.float64)},
        index=pd.DatetimeIndex(minute_index),
    )
    rule = f"{config.interval_min}min"
    # Vectorised on purpose.
    #
    # The first version aggregated through two lambdas and then walked the
    # result with ``iterrows``, building one dict per interval. For a year of
    # 50 homes across the four U20 configurations that is 2.6 million Series
    # objects, and it took three times longer than the entire physics,
    # occupancy and device simulation it was writing out. The lambdas force
    # pandas off its fast path for no gain: ``s.sum() / 60`` is the same number
    # as ``sum`` divided by 60 afterwards.
    agg = frame.resample(rule, label="left", closed="left").agg(
        import_w_sum=("import_w", "sum"),
        export_w_sum=("export_w", "sum"),
        interval_peak_w=("import_w", "max"),
        interval_min_w=("import_w", "min"),
    )
    import_wh = agg["import_w_sum"].to_numpy(dtype=np.float64) / 60.0
    export_wh = agg["export_w_sum"].to_numpy(dtype=np.float64) / 60.0
    peak_w = agg["interval_peak_w"].to_numpy(dtype=np.float64)
    min_w = agg["interval_min_w"].to_numpy(dtype=np.float64)
    starts = agg.index
    mean_w = import_wh * 60.0 / config.interval_min

    out = pd.DataFrame({
        "premises_id": (
            premises_id if config.aggregate_over == "premises"
            else f"ESTATE-{estate_id or 'UNKNOWN'}"
        ),
        "interval_start": starts,
        "interval_end": starts + pd.Timedelta(minutes=config.interval_min),
        "import_wh": import_wh,
        "export_wh": export_wh,
        "interval_peak_w": peak_w,
        "interval_min_w": min_w,
        "export_config": config.name,
        "quality": quality,
    })
    # I-067. `include_profile=False` suppresses the ENERGY SERIES, not just
    # the summary of it. It used to gate only `building_energy_profile`, so
    # `compliance_only` - described here and in design 7.8 as the
    # least-inference-risk configuration and offered as a MITIGATION for one
    # that fails the 7.8 test - exported the complete half-hourly import
    # series, summing to exactly the same 163,137,265.9 Wh as home_30min. Its
    # inference risk was identical to the configuration it was supposed to be
    # safer than, and the privacy test measured that: occupancy AUC 0.8655.
    #
    # Nothing caught it because `import_wh` IS a declared D19 field, so the
    # schema audit passed, and no occupancy or person field was present, so
    # the R09 test passed. No test asked whether a configuration differs from
    # the one it claims to be safer than.
    if not config.include_profile:
        for field in ("import_wh", "export_wh", "interval_peak_w",
                      "interval_min_w"):
            # np.nan, NOT None. `None` gives the column OBJECT dtype, and the
            # writer concatenates this frame with the profile-carrying ones:
            # today's pandas excludes an all-NA column when resolving the
            # result dtype and still gives float64, with a FutureWarning
            # saying it will stop. When it stops, D19's import_wh is written
            # as an object column and the Parquet schema changes under a
            # library upgrade - which is I-066's lesson in a different place.
            # A float NaN is unambiguous now and after.
            out[field] = np.full(len(out["interval_start"]), np.nan,
                                 dtype=np.float64)

    if config.include_profile:
        # The building energy profile R09 permits: shape information about the
        # building, with no reference to who is in it.
        out["building_energy_profile"] = [
            {
                "mean_w": round(float(m), 2),
                "peak_to_mean": round(float(p) / max(float(m), 1e-6), 3),
                "interval_min": config.interval_min,
            }
            for m, p in zip(mean_w, peak_w)
        ]
    else:
        out["building_energy_profile"] = None
    out["flex_event_id"] = flex_event_id if config.include_compliance else None
    out["flex_compliance_pct"] = (
        flex_compliance_pct if config.include_compliance else None
    )
    out = out.reset_index(drop=True)

    if config.noise_scale_wh > 0:
        # U20 option (d): home-level with calibrated noise. Built so the 7.8
        # test can measure its utility cost; NOT presented as differential
        # privacy, which design 7.8 says may only be claimed with "a defined
        # protected unit, privacy budget, composition across releases, and
        # measured utility loss" - none of which E1 establishes.
        # ``hash()`` is salted per process in CPython, so seeding from it
        # would give a different export every time the program was started -
        # silently, and only for the noisy configuration. No U20 config
        # currently sets noise_scale_wh, so this never fired; it would have
        # broken the byte-identical contract the moment one did.
        rng = np.random.default_rng(stable_entity_id(premises_id) % (2**32))
        out["import_wh"] = out["import_wh"] + rng.laplace(0.0, config.noise_scale_wh, len(out))
        out["export_wh"] = (
            out["export_wh"] + rng.laplace(0.0, config.noise_scale_wh, len(out))
        ).clip(lower=0.0)
        out["quality"] = "estimated"

    # Belt and braces: the same audit the writer will apply, applied here too,
    # so a malformed export is caught where it is built rather than at the end
    # of a long run.
    audit_frame(out.columns, "D19")
    out.attrs["claim_boundary"] = CLAIM_BOUNDARY
    out.attrs["export_config"] = config.name
    return out


def export_configurations(
    *,
    premises_id: str,
    minute_index: pd.DatetimeIndex,
    net_import_w: np.ndarray,
    net_export_w: np.ndarray,
    estate_id: str | None = None,
    **kw: Any,
) -> dict[str, pd.DataFrame]:
    """All four U20 configurations for the same underlying truth.

    Design 7.8: "build all four as configurations".  Comparing them is the
    week-3 test; building them is E1.
    """
    return {
        name: build_export(
            premises_id=premises_id, minute_index=minute_index,
            net_import_w=net_import_w, net_export_w=net_export_w,
            config=cfg, estate_id=estate_id, **kw,
        )
        for name, cfg in EXPORT_CONFIGS.items()
    }
