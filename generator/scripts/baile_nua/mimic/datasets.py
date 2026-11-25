"""D25 (mimic_export, OBS) and D26 (mimic_answer_key, GT) from a MIMIC run.

``scripts/baile_nua/schema/datasets.yaml`` is the single source of truth for
both, and this module conforms to it rather than the other way round:

* **D25** is read back out of **MIMIC's own database**, not out of the runner's
  records.  Every D25 field declares a ``mimic_field``, so the faithful source
  for "what MIMIC legitimately holds about a participant" is MIMIC.  Reading it
  back also means a field MIMIC silently dropped or rewrote shows up here
  instead of being papered over by the value the runner believed it sent.
* **D26** is the answer key the runner kept: the crosswalk to ``person_id``, the
  true traits, the planted segment, the response propensity, the
  stated-preference gap and the test-mode settings.

The crosswalk is in **D26 only**.  That is enforced twice over, and not by
review: ``person_id`` is not a declared D25 field, so
:func:`baile_nua.schema.access.assert_fields_declared` refuses it, and
``strict_columns`` refuses any undeclared column at write time.
:func:`d25_frame` never builds the column in the first place.

One schema conflict found and NOT silently resolved
---------------------------------------------------

``D25.mcv_01_to_10`` is declared ``required: true``, but MIMIC permits a
participant with no ``profile_mcv`` row at all: when MIMIC randomises
``mcv_position`` to ``post`` and the participant abandons the session, the MCV
block is never reached.  Those participants exist in MIMIC and their profiles
are valid.  Writing them as null would breach the declared schema; dropping
them would silently shrink the OBS export.  So they are written with an **empty
list**, the count is recorded in the manifest as
``mcv_block_absent_participants``, and the schema conflict is reported rather
than fixed here (``datasets.yaml`` is not mine to edit).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.io import write_dataset
from baile_nua.mimic.verify import mysql_query

__all__ = [
    "D25_FIELDS",
    "D26_FIELDS",
    "d25_frame",
    "d26_frame",
    "write_d25",
    "write_d26",
]

#: The optional FlexSense Table 3 fields MIMIC actually stores (ADR-004 applied).
_OPTIONAL_COLUMNS = (
    "education_level", "energy_bill_responsibility", "digital_access_level",
    "internet_quality", "vehicle_type", "home_automation_level",
    "community_energy_member", "occupation_sector", "primary_language",
    "social_participation_level",
)

#: D25's declared field order (datasets.yaml), used so the Parquet column order
#: is a property of the schema rather than of dictionary insertion.
D25_FIELDS = (
    "participant_id", "consent_version", "consent_granted_at", "mcv_position",
    "age_band", "reported_sex", "household_size", "children_present",
    "employment_status", "reported_work_pattern", "reported_dwelling_type",
    "ownership_status", "region_country", "region_nuts3", "urban_rural_island",
    "income_band", "der_ownership", "environmental_concern",
    "trust_in_automation", "comfort_sensitivity", "mcv_01_to_10",
    "profile_optional", "session_id", "chosen_signal",
    "chosen_display_position", "display_permutation", "latency_ms",
    "is_probe", "is_probe_repeat",
)

D26_FIELDS = (
    "participant_id", "person_id", "pool", "true_traits", "planted_segment",
    "planted_null_mode", "response_propensity", "stated_gap", "satisficer",
    "planted_position_bias", "planted_context_effect", "generator", "gc_mode",
    "simulated_session_date", "test_mode_settings",
)

_NULL = ("NULL", "")


def _rows(sql: str, columns: list[str]) -> pd.DataFrame:
    """One MySQL query as a frame, with MySQL's batch-mode NULLs restored."""
    raw = mysql_query(sql)
    out: list[list[Any]] = []
    for r in raw:
        if len(r) != len(columns):           # pragma: no cover - defensive
            raise RuntimeError(
                f"expected {len(columns)} columns, got {len(r)}: {r[:4]}"
            )
        out.append([None if v in _NULL else v for v in r])
    return pd.DataFrame(out, columns=columns)


def _json_or_none(v: Any) -> str | None:
    """Keep a MIMIC JSON column as a canonical JSON string.

    Stored as text rather than as a Parquet struct or list: the column is
    declared ``json`` and its shape varies between participants (``der_ownership``
    is a list, ``display_permutation`` a mapping), and a text column hashes and
    round-trips identically everywhere.
    """
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return json.dumps(json.loads(v), sort_keys=True, separators=(",", ":"))
        except (ValueError, TypeError):
            return v
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _int_or_none(v: Any) -> int | None:
    return None if v is None else int(v)


# --------------------------------------------------------------------------- #
# D25
# --------------------------------------------------------------------------- #

def d25_frame(*, predicate: str = "consent_version LIKE 'SYNTHETIC%'") -> tuple[pd.DataFrame, dict[str, Any]]:
    """D25 at its declared grain (participant, session, response), from MIMIC.

    A participant who abandoned before answering anything still appears, once,
    with null session and response fields: the grain is participant-session-
    response and a participant MIMIC holds is not dropped because they answered
    nothing.
    """
    prof_cols = [
        "participant_id", "consent_version", "consent_granted_at", "mcv_position",
        "age_band", "reported_sex", "household_size", "children_present",
        "employment_status", "reported_work_pattern", "reported_dwelling_type",
        "ownership_status", "region_country", "region_nuts3",
        "urban_rural_island", "income_band", "der_ownership",
        "environmental_concern", "trust_in_automation", "comfort_sensitivity",
        *[f"mcv_{i:02d}" for i in range(1, 11)],
        *_OPTIONAL_COLUMNS,
    ]
    profiles = _rows(
        "SELECT p.participant_id, p.consent_version, "
        "DATE_FORMAT(p.consent_granted_at, '%Y-%m-%dT%H:%i:%SZ'), p.mcv_position, "
        "p.age_band, p.sex, p.household_size, p.children_present, "
        "p.employment_status, p.work_pattern, p.dwelling_type, "
        "p.ownership_status, p.region_country, p.region_nuts3, "
        "p.urban_rural_island, p.income_band, p.der_ownership, "
        "p.environmental_concern, p.trust_in_automation, p.comfort_sensitivity, "
        + ", ".join(f"m.mcv_{i:02d}" for i in range(1, 11)) + ", "
        + ", ".join(f"o.{c}" for c in _OPTIONAL_COLUMNS) +
        " FROM profiles p "
        " LEFT JOIN profile_mcv m ON m.participant_id = p.participant_id "
        " LEFT JOIN profile_optional o ON o.participant_id = p.participant_id "
        f" WHERE p.{predicate} ORDER BY p.participant_id",
        prof_cols,
    )
    resp_cols = [
        "participant_id", "session_id", "session_item_id", "chosen_signal",
        "chosen_display_position", "display_permutation", "latency_ms",
        "is_probe", "is_probe_repeat",
    ]
    responses = _rows(
        "SELECT r.participant_id, r.session_id, r.session_item_id, "
        "r.chosen_signal, r.chosen_display_position, r.display_permutation, "
        "r.latency_ms, r.is_probe, r.is_probe_repeat "
        "FROM responses r INNER JOIN profiles p "
        "  ON p.participant_id = r.participant_id "
        f" WHERE p.{predicate} "
        "ORDER BY r.participant_id, r.session_id, r.session_item_id",
        resp_cols,
    )

    mcv_cols = [f"mcv_{i:02d}" for i in range(1, 11)]
    absent = int(profiles[mcv_cols].isna().all(axis=1).sum())
    profiles["mcv_01_to_10"] = [
        [] if all(v is None for v in row) else [int(v) for v in row]
        for row in profiles[mcv_cols].itertuples(index=False, name=None)
    ]
    # A participant who answered none of the ten optional items has no
    # profile_optional row at all, which is null rather than "{}": an empty
    # object would say MIMIC holds an empty record, and it holds none.
    profiles["profile_optional"] = [
        _json_or_none(d) if (d := {
            k: v for k, v in zip(_OPTIONAL_COLUMNS, row) if v is not None
        }) else None
        for row in profiles[list(_OPTIONAL_COLUMNS)].itertuples(index=False, name=None)
    ]
    profiles["der_ownership"] = profiles["der_ownership"].map(_json_or_none)
    for c in ("environmental_concern", "trust_in_automation", "comfort_sensitivity"):
        profiles[c] = profiles[c].map(_int_or_none)

    responses["display_permutation"] = responses["display_permutation"].map(_json_or_none)
    # ``session_item_id`` included: MySQL's batch mode returns every column as
    # text, and sorting item ids as text puts item 10 before item 9.
    for c in ("session_item_id", "chosen_display_position", "latency_ms"):
        responses[c] = responses[c].map(_int_or_none)
    for c in ("is_probe", "is_probe_repeat"):
        responses[c] = responses[c].map(lambda v: None if v is None else bool(int(v)))

    keep_profile = [c for c in D25_FIELDS if c in profiles.columns]
    frame = profiles[keep_profile].merge(
        responses, on="participant_id", how="left", sort=False,
    )
    # Ordered by ITEM, not by screen position. ``session_item_id`` is MIMIC's
    # own auto-increment on ``session_items`` and so follows the order the
    # items were created and answered in; it is kept only to sort by and then
    # dropped, because it is not a declared D25 field. Sorting on
    # ``chosen_display_position`` instead - which is where the chosen option
    # happened to appear on screen, 1 to 4 - would group a session's thirteen
    # responses into four blocks in an order that means nothing.
    frame = frame.sort_values(
        ["participant_id", "session_id", "session_item_id"],
        na_position="last", kind="stable",
    ).reset_index(drop=True)
    frame = frame.reindex(columns=list(D25_FIELDS))

    diagnostics = {
        "source": "MIMIC MySQL via the public instance's own tables",
        "predicate": predicate,
        "n_participants": int(len(profiles)),
        "n_responses": int(len(responses)),
        "rows": int(len(frame)),
        "participants_with_no_response": int(
            len(profiles) - responses["participant_id"].nunique()
        ),
        "mcv_block_absent_participants": absent,
        "mcv_block_absent_note": (
            "D25.mcv_01_to_10 is declared required:true, but MIMIC permits a "
            "participant with no profile_mcv row (mcv_position='post' and the "
            "session abandoned before the block). Those are written as an empty "
            "list and counted here; datasets.yaml should declare the field "
            "required:false. Reported, not fixed."
        ),
        "crosswalk_present": False,
        "crosswalk_note": (
            "person_id is not a declared D25 field, so the schema's own "
            "assert_fields_declared refuses it; the crosswalk lives in D26."
        ),
    }
    return frame, diagnostics


# --------------------------------------------------------------------------- #
# D26
# --------------------------------------------------------------------------- #

def d26_frame(
    answer_keys: list[dict[str, Any]],
    *,
    planted_context_effect: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """D26 at its declared grain (participant), from the runner's answer keys."""
    rows: list[dict[str, Any]] = []
    for k in answer_keys:
        if not k.get("participant_id"):
            continue                 # consent never granted: no participant row
        rows.append({
            "participant_id": k["participant_id"],
            "person_id": k["person_id"],
            "pool": k["pool"],
            "true_traits": _json_or_none(k["true_traits"]),
            "planted_segment": k.get("planted_segment"),
            "planted_null_mode": bool(k.get("planted_null_mode", False)),
            "response_propensity": float(k["response_propensity"]),
            "stated_gap": float(k["stated_gap"]),
            "satisficer": bool(k["satisficer"]),
            "planted_position_bias": float(k.get("planted_position_bias", 0.0)),
            "planted_context_effect": _json_or_none(planted_context_effect),
            "generator": k.get("generator", "G-B"),
            "gc_mode": k.get("gc_mode"),
            "simulated_session_date": k.get("simulated_session_date"),
            "test_mode_settings": _json_or_none({
                **(k.get("test_mode_settings") or {}),
                "gb_spec_hash": k.get("gb_spec_hash"),
                "wave": k.get("wave"),
                "n_waves": k.get("n_waves"),
                "wave_person_key": k.get("wave_person_key"),
                "u18_information_lost": k.get("u18_information_lost") or [],
            }),
        })
    frame = pd.DataFrame(rows, columns=list(D26_FIELDS))
    frame = frame.sort_values(
        ["person_id", "simulated_session_date", "participant_id"],
        na_position="last", kind="stable",
    ).reset_index(drop=True)

    dated = frame["simulated_session_date"].notna()
    by_person = frame.groupby("person_id")["participant_id"].count()
    panel = frame[frame["pool"] == "BN-panel"]
    diagnostics = {
        "rows": int(len(frame)),
        "n_distinct_persons": int(frame["person_id"].nunique()),
        "n_dated": int(dated.sum()),
        "n_undated": int((~dated).sum()),
        "linked_panel_rows": int(len(panel)),
        "linked_panel_persons": int(panel["person_id"].nunique()),
        "linked_panel_rows_dated": int(panel["simulated_session_date"].notna().sum()),
        "linked_panel_rows_undated": int(panel["simulated_session_date"].isna().sum()),
        "max_rows_per_person": int(by_person.max()) if len(by_person) else 0,
        "simulated_session_date_span": (
            [str(frame.loc[dated, "simulated_session_date"].min()),
             str(frame.loc[dated, "simulated_session_date"].max())]
            if dated.any() else []
        ),
        "crosswalk_present": True,
        "carries": [
            "crosswalk (person_id)", "true_traits", "planted_segment",
            "response_propensity", "stated_gap", "planted_position_bias",
            "planted_context_effect", "simulated_session_date",
            "test_mode_settings",
        ],
    }
    return frame, diagnostics


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def _write(frame: pd.DataFrame, dataset_id: str, root: Path, package: str,
           extra: dict[str, Any], part: int = 0) -> Path:
    path = Path(root) / "v1" / package / f"{dataset_id}_part{part:03d}.parquet"
    return write_dataset(
        frame, dataset_id, path,
        extra_meta={"part": part, "streamed": False, **extra},
    )


def write_d25(frame: pd.DataFrame, root: Path, *, extra: dict[str, Any] | None = None,
              part: int = 0) -> Path:
    return _write(frame, "D25", root, "observable", extra or {}, part)


def write_d26(frame: pd.DataFrame, root: Path, *, extra: dict[str, Any] | None = None,
              part: int = 0) -> Path:
    return _write(frame, "D26", root, "ground_truth", extra or {}, part)
