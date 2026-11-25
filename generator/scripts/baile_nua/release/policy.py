"""What the release package materialises, and what it renders on demand.

U28, ruling of 9 October 2026, applying **R13** in full: *"Ground truth is
stored as events plus seeds, with 1 Hz and coarser data rendered
deterministically on demand."*

E1 did not apply R13.  It materialised D18 at one-minute resolution for every
home and every channel, which came to 66.1 million rows and 531 MB for one
estate-year — and projected to **232 GB** for the ten-year town against 74 GiB
of real disk (I-036).  The materialised 1-minute series was never the ground
truth; the events and the seed tree are.  The series is a *rendering* of them,
and R13 says so.

**What the release package holds** (U28 clause 2):

================================================  =====================
Smart-meter series, 30-minute, every home         materialised
D19 export views, 15-minute                       materialised
D18 1-minute channels, tiers T3 and T4            materialised
D18 1-minute channels, 6.4 item 6 sub-metered set  materialised
Everything else, including 1 Hz                   rendered on demand
================================================  =====================

**What makes this safe rather than merely smaller.** Three things, and none of
them is a promise:

*The events survive.* D13 appliance cycles carry `signature_id`,
`signature_seed`, start, end and energy. D18 is a deterministic function of
those plus the seed tree, and `render_cycle` is already tested byte-identical
for a fixed seed (NC-D5-02 plants a non-deterministic render and must be
rejected). Nothing that can be rendered is lost; it is derivable.

*The privacy work is unaffected.* Design 7.8's inference tests run on the
**export views**, which are 15- and 30-minute aggregates, and those are
materialised in full for every home (U28 clause 3). The attack surface the
privacy threat model is about is exactly what is kept.

*The checks still see everything.* The V0 invariants on D16 — physics bounds
and the indoor-temperature distribution — run over the **stream** during the
run, where every home and every minute passes through, not over the released
file. Materialising less does not check less. That distinction is the one that
matters: a package that is smaller because it was checked less would be worse
than a large one.

**What is genuinely given up.** A consumer of the package who wants 1-minute
data for a T1 home must re-render it, which needs this code and the seed, not
just the Parquet. That is R13's intended trade and it is stated in the
package's own manifest rather than left to be discovered.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

__all__ = [
    "MATERIALISATION_POLICY",
    "PackageProjection",
    "project_package",
    "write_projection",
]

#: Per dataset: what is materialised, at what interval, for which homes.
#:
#: ``share_of_homes`` is resolved against the sensor-tier mix at run time, so
#: this table does not hard-code a tier distribution that the synthesis owns.
MATERIALISATION_POLICY: dict[str, dict[str, Any]] = {
    "D13": {
        "what": "appliance cycle events",
        "interval": "event",
        "homes": "all",
        "materialised": True,
        "why": (
            "These ARE the ground truth under R13. Everything D18 contains at "
            "any resolution is rendered from these plus the seed tree, so they "
            "are the one thing that cannot be dropped."
        ),
    },
    "D11": {
        "what": "presence intervals",
        "interval": "event",
        "homes": "all",
        "materialised": True,
        "why": (
            "Events, and small: 14 days of the estate came to 463 kB. The "
            "presence invariant is checked on them."
        ),
    },
    "D16": {
        "what": "building thermal and CO2 state",
        "interval": "15 minutes",
        "homes": "sensored",
        "materialised": True,
        "why": (
            "Materialised only where there is a sensor that could have "
            "observed it, which is the 6.5 rule for an observable view and the "
            "honest subset for a ground-truth one. The V0 invariants run over "
            "the full STREAM during the run, so restricting the released file "
            "does not restrict the checking."
        ),
    },
    "D18_meter": {
        "what": "smart-meter import and export",
        "interval": "30 minutes",
        "homes": "all",
        "materialised": True,
        "channels": 2,
        "why": (
            "U28 clause 2: every home has a meter, and 30 minutes is what an "
            "Irish smart meter actually records. This is the series most "
            "research uses."
        ),
    },
    "D18_sensored": {
        "what": "full sensor channel set at high rate",
        "interval": "1 minute, 1 Hz on demand",
        "homes": "T3, T4 and the 6.4 sub-metered subset",
        "materialised": True,
        "why": (
            "U28 clause 2. These are the homes where a real study installed "
            "equipment capable of producing it, which is also what 6.5 rule 1 "
            "requires of an observable field: a named mechanism that would "
            "have produced it."
        ),
    },
    "D18_sensored_fallback": {
        "what": (
            "full sensor channel set at high rate, SUB-METERED COHORT ONLY"
        ),
        "interval": "1 minute, 1 Hz on demand",
        "homes": "the 6.4 item 6 labelled sub-metered subset only",
        "materialised": True,
        "why": (
            "The storage fallback (U28 amendment, 9 October). When no external "
            "drive is attached, T3 and T4 one-minute channels are rendered on "
            "demand too, and only the labelled sub-metered subset is "
            "materialised at one minute. That subset is the one 6.4 item 6 "
            "exists for - supervised training data for NILM and occupancy - "
            "so it is the part that a consumer cannot reconstruct the VALUE "
            "of from a render, because its value is the installer's labels "
            "and its mislabelled and failed channels, not the series."
        ),
    },
    "D19": {
        "what": "edge export views, all four U20 configurations",
        "interval": "15 and 30 minutes",
        "homes": "all",
        "materialised": True,
        "why": (
            "U28 clause 3: the 7.8 privacy inference tests run on these, so "
            "they are kept in full for every home. Dropping them would move "
            "the privacy question out of reach, which is the opposite of what "
            "a smaller package should do."
        ),
    },
}


@dataclasses.dataclass
class PackageProjection:
    """A storage projection for one package configuration."""

    label: str
    n_homes: int
    n_years: int
    by_dataset: dict[str, dict[str, Any]]
    total_bytes: float
    margin: float

    @property
    def total_gb(self) -> float:
        return self.total_bytes / 1024**3

    @property
    def total_gb_with_margin(self) -> float:
        return self.margin * self.total_gb

    def as_row(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_homes": self.n_homes,
            "n_years": self.n_years,
            "total_gb": round(self.total_gb, 2),
            "margin": self.margin,
            "total_gb_with_margin": round(self.total_gb_with_margin, 2),
            "by_dataset": self.by_dataset,
        }


def _rows_per_channel_day(measured: dict[str, dict[str, Any]],
                          estate_channels: float, days: int) -> float:
    """Measured D18 rows per channel-day, from the E1 run.

    Derived rather than assumed: E1's 66,097,553 D18 rows over 156 channels and
    365 days give 1,160.6 rows per channel-day, against the 1,440 minutes a day
    contains. The shortfall is the observation models dropping readings -
    reporting interval, bursty gaps, dropouts - and it carries through any
    projection of the same layer.
    """
    return float(measured["D18"]["rows"]) / max(estate_channels * days, 1.0)


def _channels_per_home(
    tier_mix: dict[str, float], channels_per_tier: dict[str, int],
    *, tiers: tuple[str, ...] | None = None,
) -> float:
    """Expected sensor channels per home, over the given tiers."""
    keys = tiers if tiers is not None else tuple(channels_per_tier)
    total = sum(tier_mix.get(t, 0.0) for t in tier_mix)
    if total <= 0:
        return 0.0
    return sum(
        (tier_mix.get(t, 0.0) / total) * channels_per_tier.get(t, 0) for t in keys
    )


def project_package(
    *,
    measured: dict[str, dict[str, Any]],
    n_homes: int,
    n_years: int,
    tier_mix: dict[str, float],
    channels_per_tier: dict[str, int],
    estate_channels: float,
    sensored_tiers: tuple[str, ...] = ("T3", "T4"),
    sub_metered_extra_channels: int = 8,
    n_sub_metered_town: int = 35,
    n_town_homes: int = 1092,
    margin: float = 1.5,
    apply_u28: bool = True,
    storage_fallback: bool = False,
    presence_days_per_year: int = 14,
    measured_homes: int = 50,
    measured_days: int = 365,
    label: str = "",
) -> PackageProjection:
    """Project a package's size by scaling the E1 measurement.

    Every rate is a measured row count divided by the home-days or
    channel-days that produced it, so the pre-U28 estate-year case reproduces
    the E1 figure rather than approximating it - which is the check that the
    projection machinery is sound before it is used on a configuration nobody
    has run.

    ``apply_u28=False`` reproduces the pre-ruling policy, so the two are
    directly comparable.
    """
    bpr = {k: float(v["bytes_per_row"]) for k, v in measured.items()}
    home_days = n_homes * 365 * n_years
    measured_home_days = measured_homes * measured_days
    rpcd = _rows_per_channel_day(measured, estate_channels, measured_days)
    out: dict[str, dict[str, Any]] = {}

    def add(key: str, rows: float, bytes_key: str, note: str) -> None:
        by = rows * bpr[bytes_key]
        out[key] = {
            "rows": round(rows), "bytes": round(by),
            "gb": round(by / 1024**3, 3),
            "bytes_per_row_measured": bpr[bytes_key], "note": note,
        }

    # ---- events: R13's ground truth, materialised whatever the policy ----
    add("D13", measured["D13"]["rows"] / measured_home_days * home_days, "D13",
        "appliance cycle events: R13's ground truth, and what D18 is rendered "
        "from. Materialised in full under either policy.")
    add("D11",
        measured["D11"]["rows"] / (measured_homes * presence_days_per_year)
        * n_homes * presence_days_per_year * n_years,
        "D11", f"presence events, {presence_days_per_year} days a year")

    # ---- the sub-metered subset is a fixed TOWN cohort at tier T4 --------
    #
    # 6.4 item 6: "20 to 50 homes with appliance-level channels... Extra D18
    # channels at tier T4". So it is not a share of whatever slice is being
    # projected - applying it that way made a 50-home estate 70% sub-metered
    # and produced a U28 estate LARGER than the pre-U28 one, which is how the
    # bug announced itself.
    sub_metered_here = n_sub_metered_town * min(n_homes / max(n_town_homes, 1), 1.0)

    if apply_u28:
        # D16: 15-minute state for the sensored homes only.
        if storage_fallback:
            # Only where one-minute data is kept, for the same reason.
            sensored_share = min(sub_metered_here / max(n_homes, 1), 1.0)
        else:
            sensored_share = sum(
                tier_mix.get(t, 0.0) for t in sensored_tiers
            ) / max(sum(tier_mix.values()), 1e-9)
        add("D16",
            measured["D16"]["rows"] / measured_home_days
            * n_homes * sensored_share * 365 * n_years,
            "D16",
            f"15-minute state for the {sensored_share:.0%} of homes with a "
            f"sensor that could have observed it. The V0 invariants run over "
            f"the full stream during the run, so this restricts the released "
            f"file and not the checking.")

        # D18, part one: a 30-minute meter for every home.
        add("D18_meter", n_homes * 2 * 48 * 365 * n_years, "D18",
            "smart-meter import and export at 30 minutes, every home (U28 "
            "clause 2). 30 minutes is what an Irish smart meter records.")

        # D18, part two: the full channel set at 1 minute.
        #
        # Two policies. As ruled, that is tiers T3 and T4 plus the sub-metered
        # cohort's extra appliance channels. Under the storage fallback it is
        # the sub-metered cohort ALONE, with T3 and T4 rendered on demand like
        # everything else.
        extra_channels = sub_metered_here * sub_metered_extra_channels
        if storage_fallback:
            sub_metered_own = sub_metered_here * channels_per_tier.get("T4", 10)
            add("D18_sensored",
                (sub_metered_own + extra_channels) * 365 * n_years * rpcd, "D18",
                f"STORAGE FALLBACK: one-minute data for the "
                f"{sub_metered_here:.0f}-home labelled sub-metered subset only "
                f"({channels_per_tier.get('T4', 10)} tier-T4 channels plus "
                f"{sub_metered_extra_channels} appliance-level channels). "
                f"Tiers T3 and T4 are rendered on demand, byte-identically.")
        else:
            sensored_channels = n_homes * _channels_per_home(
                tier_mix, channels_per_tier, tiers=sensored_tiers
            )
            add("D18_sensored",
                (sensored_channels + extra_channels) * 365 * n_years * rpcd, "D18",
                f"full channel set at 1 minute for tiers {sensored_tiers}, plus "
                f"{sub_metered_extra_channels} appliance-level channels on the "
                f"{sub_metered_here:.0f}-home sub-metered cohort (6.4 item 6). "
                f"1 Hz on demand from the same events.")
    else:
        add("D16", measured["D16"]["rows"] / measured_home_days * home_days,
            "D16", "15-minute state, every home (pre-U28)")
        all_channels = n_homes * _channels_per_home(tier_mix, channels_per_tier)
        add("D18", all_channels * 365 * n_years * rpcd, "D18",
            "every channel of every tier at 1 minute, every home (pre-U28)")

    # ---- D19 kept in full either way: 7.8 depends on it -----------------
    add("D19", measured["D19"]["rows"] / measured_home_days * home_days, "D19",
        "all four U20 export configurations at 15 and 30 minutes. U28 clause "
        "3 keeps these because the 7.8 privacy inference tests run on them.")

    total = float(sum(v["bytes"] for v in out.values()))
    return PackageProjection(
        label=label or ("U28 render-on-demand" if apply_u28 else "pre-U28"),
        n_homes=n_homes, n_years=n_years, by_dataset=out,
        total_bytes=total, margin=margin,
    )


def write_projection(
    *, out_path: Path, free_bytes: int | None = None
) -> dict[str, Any]:
    """Re-project the ten-year town package under U28 and report whether it fits."""
    import shutil

    from baile_nua import CLAIM, LABEL
    from baile_nua.observation.sensors import TIER_DEVICES
    from baile_nua.population.buildings import SENSOR_TIER_UPTAKE

    diag = json.loads(
        (Path(__file__).resolve().parents[3] / "v1" / "run_diagnostics.json")
        .read_text(encoding="utf-8")
    )
    measured = diag["benchmark"]["storage"]["by_dataset"]
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    n_town = int(diag["benchmark"]["full_town_projection"]["n_town_homes"])

    if free_bytes is None:
        free_bytes = shutil.disk_usage("/").free

    # The estate's OWN tier mix, for the case that must reproduce the
    # measurement: the town uptake is a different distribution and using it
    # here would make the self-check pass or fail for the wrong reason.
    estate_tiers = diag["slice"]["sensor_tiers"]
    estate_mix = {k: float(v) for k, v in estate_tiers.items()}
    estate_channels = sum(
        estate_mix.get(t, 0) * channels.get(t, 0) for t in channels
    )

    cases = []
    for label, homes, years, u28, mix, n_sub in (
        ("estate-year, pre-U28 (reproduces the E1 measurement)",
         50, 1, False, estate_mix, 0),
        ("estate-year, U28", 50, 1, True, estate_mix, 0),
        ("town-year, pre-U28", n_town, 1, False, SENSOR_TIER_UPTAKE, 35),
        ("town-year, U28", n_town, 1, True, SENSOR_TIER_UPTAKE, 35),
        ("estate ten years, U28", 50, 10, True, estate_mix, 0),
        ("town ten years, pre-U28", n_town, 10, False, SENSOR_TIER_UPTAKE, 35),
        ("town ten years, U28", n_town, 10, True, SENSOR_TIER_UPTAKE, 35),
    ):
        cases.append(project_package(
            measured=measured, n_homes=homes, n_years=years,
            tier_mix=mix, channels_per_tier=channels,
            estate_channels=estate_channels,
            n_sub_metered_town=n_sub, n_town_homes=n_town,
            apply_u28=u28, label=label,
        ).as_row())

    # The storage fallback: no external drive, so T3/T4 one-minute channels are
    # rendered on demand too and only the sub-metered subset is materialised.
    cases.append(project_package(
        measured=measured, n_homes=n_town, n_years=10,
        tier_mix=SENSOR_TIER_UPTAKE, channels_per_tier=channels,
        estate_channels=estate_channels, n_sub_metered_town=35,
        n_town_homes=n_town, apply_u28=True, storage_fallback=True,
        label="town ten years, U28 + storage fallback",
    ).as_row())

    # Self-check: the pre-U28 estate-year case must reproduce what E1 measured.
    measured_gb = diag["benchmark"]["storage"]["total_bytes"] / 1024**3
    reproduced = cases[0]["total_gb"]
    if abs(reproduced - measured_gb) / max(measured_gb, 1e-9) > 0.02:
        raise RuntimeError(
            f"the projection does not reproduce its own basis: pre-U28 "
            f"estate-year comes out at {reproduced:.3f} GB against a measured "
            f"{measured_gb:.3f} GB. Fix the projection before trusting any "
            f"other case."
        )

    target = next(c for c in cases if c["label"] == "town ten years, U28")
    fallback = next(
        c for c in cases if c["label"] == "town ten years, U28 + storage fallback"
    )
    before = next(c for c in cases if c["label"] == "town ten years, pre-U28")

    # Which policy applies is decided by whether a GENUINELY external drive is
    # attached - never by a volume's own claim to be one (I-036).
    from baile_nua.release.storage import storage_report

    needed = int(target["total_gb_with_margin"] * 1024**3)
    storage = storage_report(required_bytes=needed)
    external = storage["external_drive_found"]
    applicable = target if external else fallback
    free_gb = (
        storage["external_drive"]["free_gb"] if external
        else free_bytes / 1024**3
    )
    fits = applicable["total_gb_with_margin"] <= free_gb

    out = {
        "label": LABEL,
        "claim": CLAIM,
        "design_ref": "R13; U28 ruling of 9 October 2026; I-036; 6.4 item 6; 7.8",
        "policy": MATERIALISATION_POLICY,
        "measured_basis": {
            "source": "v1/run_diagnostics.json, the E1 estate-year run",
            "homes": 50, "days": 365,
            "by_dataset": measured,
            "realised_fraction_of_channel_minutes": 0.806,
            "realised_fraction_note": (
                "Measured: E1 wrote 66,097,553 D18 rows where the channel mix "
                "implies 82,005,000 channel-minutes, because the observation "
                "models drop readings. Carried through every projection."
            ),
        },
        "projections": cases,
        "storage": storage,
        "policy_applicable": applicable["label"],
        "verdict": {
            "external_drive_attached": external,
            "policy_applied": applicable["label"],
            "ten_year_town_gb_applicable": applicable["total_gb"],
            "ten_year_town_gb_with_margin_applicable":
                applicable["total_gb_with_margin"],
            "ten_year_town_gb_fallback": fallback["total_gb"],
            "ten_year_town_gb_with_margin_fallback":
                fallback["total_gb_with_margin"],
            "ten_year_town_gb_before": before["total_gb"],
            "ten_year_town_gb_with_margin_before": before["total_gb_with_margin"],
            "ten_year_town_gb_after": target["total_gb"],
            "ten_year_town_gb_with_margin_after": target["total_gb_with_margin"],
            "reduction_factor": round(
                before["total_gb_with_margin"]
                / max(applicable["total_gb_with_margin"], 1e-9), 2
            ),
            "free_gb_measured_now": round(free_gb, 1),
            "margin": 1.5,
            "fits": bool(fits),
            "decision": (
                "PROCEED to the full ten-year town run in week 3"
                if fits else
                "STOP before the full ten-year town run and report (U28 clause 4)"
            ),
        },
        "what_is_given_up": (
            "A consumer wanting 1-minute data for a T1 or T2 home must "
            "re-render it from the events and the seed, which needs this code "
            "and not only the Parquet. That is R13's intended trade. It is "
            "recorded in the package manifest rather than left to be "
            "discovered, and the render is byte-identical for a fixed seed - "
            "NC-D5-02 plants a non-deterministic render and must be rejected."
        ),
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return out
