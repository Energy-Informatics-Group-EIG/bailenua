"""Why a declared dataset is NOT written, per dataset, in one place.

Design 6.1 declares 31 datasets.  The frozen engine produces the state for
some of them and not for others, and the difference matters: a reader cannot
tell a dataset that the model never had from one the exporter forgot.  So
every dataset this package does not write has an entry here, and
:func:`baile_nua.export.run.export_all` returns them alongside the ones it
did write.

The rule the entries obey: **no row is invented.**  Where a required field has
no model behind it, the dataset stays absent and the field that is missing is
named.  Lowering the schema to fit what exists, or filling a required field
with a plausible number, would both turn an absence into a claim.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ABSENT", "OWNED_ELSEWHERE", "SUPERSEDED", "reason_for"]

#: Datasets another agent owns.  Not a gap, and not this package's to write.
#: I-102. D10 and D17 were HERE until v1-engine-freeze-2, with reasons saying an
#: ENGINE change was needed to write them. That change was made and is what the
#: freeze IS: `engine.run` carries the day's activity intervals on DayResult and
#: `stream_writer` buffers them and the per-epoch network rows. Both are now in
#: `dispatch.WRITTEN_BY_THE_ENGINE`, so a run that streamed them has them and a
#: run that did not is reported from its own storage report rather than from a
#: stale claim here.
#:
#: The C1/C2 distinction the old D17 reason carried is still real and is worth
#: keeping: D17's p_kw, q_kvar, voltage_pu and loading_pct come from
#: `network.lv.d17_rows`, which reads a SOLVED pandapower net. The estate-year
#: runs coupling mode C1 and does not solve a power flow, so it carries no D17
#: however new the engine is - measured on the freeze-2 re-run, which wrote D10
#: but no D17. Only a C2 run carries D17; the 14-day town run is the C2 one, and
#: under freeze-2 it writes D17 (157,248 rows) and D17_aggregate (158,340).
OWNED_ELSEWHERE: dict[str, str] = {
    "D25": "MIMIC participant panel; owned by the MIMIC exporter, not by this package",
    "D26": "MIMIC answer key; owned by the MIMIC exporter, not by this package",
}

#: ``dataset_id -> {verdict, reason, missing_required, needs}``.
#:
#: ``needs`` says what would have to change for the dataset to become
#: writable, and it is deliberately explicit about when that change is a MODEL
#: change: the model is frozen, so a model change is a decision for the
#: coordinator and not something an exporter may make.
ABSENT: dict[str, dict[str, Any]] = {
    "D12": {
        "verdict": "not written",
        "reason": (
            "Trips are not retained either. `activity.engine` computes travel "
            "for the EV state of charge (its own comment says so at the one "
            "place D12 is named in the package), and no trip row survives the "
            "day: DayResult has no trips field and StreamWriter has no D12 "
            "buffer."
        ),
        "missing_required": [
            "trip_id", "person_id", "start", "end", "origin_id",
            "destination_id", "mode", "distance_km", "purpose",
        ],
        "needs": "an ENGINE change, as D10. Reported, not made.",
    },
}



#: The verdicts above that were ANSWERED rather than overturned.
#:
#: D04, D21, D23, D24 and D27 were each recorded here as "not written", and
#: each reason was correct about the state of the package when it was written.
#: They are lifted because the gap each named was closed, and the superseded
#: reason is kept verbatim so that a reader can check the answer against the
#: objection instead of taking the removal on trust.
#:
#: D04 and D24 are a different KIND of answer from the other three and the
#: difference matters.  D21, D23 and D27 are now complete: nothing they declare
#: is missing.  D04 and D24 are written with required columns still null,
#: because the objection each carried was partly right - and a null with the
#: reason attached to the row is a stronger statement of that objection than an
#: absent dataset, which says nothing about the eleven or the twelve columns
#: that WERE available.  Neither schema was lowered and no value was invented:
#: the nulls go through ``write_dataset(null_required=...)``, which puts them
#: and their reasons in the part's own manifest.
SUPERSEDED: dict[str, dict[str, str]] = {
    "D04": {
        "was": (
            "no model for make_model_synth or failure_hazard_scale, so the "
            "dataset stays absent rather than inventing a parameter the "
            "physics never saw"
        ),
        "answered_by": (
            "baile_nua.export.assets, which does not invent either of them. "
            "Both are still null, and so are install_date and age_years_at_t0 "
            "for the five asset classes that carry no date - each named in "
            "assets.NULL_REQUIRED with its reason and recorded in the part's "
            "own manifest. What the old reason did not establish is that the "
            "REST of D04 is unavailable: the engine draws an appliance stock "
            "with ages, draws PV with a capacity, an azimuth and a tilt, and "
            "builds the battery, the vehicle and the charger from named "
            "constants, and the run's own D13 rows say which signature each "
            "appliance keys into. Those rows are now written and the two gaps "
            "the objection named are visible IN them instead of standing in "
            "place of them."
        ),
    },
    "D24": {
        "was": (
            "five required fields with no source anywhere in the build, and a "
            "META release package outside the paths the export was permitted "
            "to write"
        ),
        "answered_by": (
            "baile_nua.export.calibration_targets, which fills the eleven "
            "columns the old entry's own field_mapping said could be filled "
            "and leaves the five it said could not - domain, tolerance, "
            "tolerance_kind, evidence_tag, provisional - null by declaration, "
            "with the reason per field in the part's manifest. The schema "
            "finding is unchanged and is now carried by the data. The "
            "packaging half of the objection is simply gone: the per-year "
            "replay export creates <year>/pkg/evidence/ before it calls "
            "export_all, as it must for D22 and D23, so a META dataset can be "
            "placed."
        ),
    },
    "D21": {
        "was": (
            "no narrative generator in the package; writing prose here would "
            "be free-written text, which the field's own note forbids"
        ),
        "answered_by": (
            "baile_nua.export.biographies, which renders one templated "
            "sentence per structured fact and carries the record ids each "
            "sentence came from, inline in the Markdown and in "
            "source_record_ids. Nothing is free-written: the generator "
            "refuses a sentence with no citation, and the schema test "
            "resolves every cited id to a row of the written part it names."
        ),
    },
    "D23": {
        "was": (
            "the runs recorded no code SHA or tree hash, and computing them "
            "now would describe the exporter's commit rather than the run's"
        ),
        "answered_by": (
            "baile_nua.export.run_manifest, which does not compute them for "
            "the current tree. Every field carries a provenance CLASS, and "
            "the reconstructed ones are reconstructed from the nearest commit "
            "at or before the run's start and suffixed '-reconstructed'. The "
            "objection stands as stated and is recorded in the data: the "
            "freeze tag is demonstrably NOT the runs' code, and which files "
            "differ is in the row."
        ),
    },
    "D27": {
        "was": (
            "no tariff or contract model, and the only tariff-adjacent "
            "declared source (CSO MEC05) carries no rates"
        ),
        "answered_by": (
            "baile_nua.export.tariffs, which writes the card as a RECORD "
            "ONLY: the structure is read from three declared sources and "
            "every magnitude is an assumption with a search record. MEC05 "
            "indeed carries no rates, and neither does anything else in the "
            "corpus - which is why the card is unit-normalised rather than "
            "priced."
        ),
    },
}
#: The reasons as they stood, kept verbatim.
SUPERSEDED_VERBATIM: str = """    "D04": {
        "verdict": "not written",
        "reason": (
            "The frozen engine's appliance stock is drawn by "
            "`engine.e1_run._draw_stock`, which carries three fields per asset: "
            "`asset_id`, `age_years` and `rated_power_w` (always 0.0, a "
            "placeholder - the power comes from the signature library at render "
            "time, not from the asset record). D04 declares "
            "`make_model_synth` and `failure_hazard_scale` as REQUIRED, and "
            "neither has any model in E1: there is no model label driving "
            "signature variation, and appliance failure is modelled as a "
            "fixed seven-day out-of-service disruption "
            "(`engine.run` sets `failed_appliances[k] = sim_day + 7`), not as "
            "a Weibull lifetime. Writing either would be inventing a "
            "parameter the physics never saw."
        ),
        "missing_required": ["make_model_synth", "failure_hazard_scale"],
        "needs": (
            "a MODEL change: a per-asset make/model label and a Weibull "
            "failure hazard in devices/appliances.py. Reported, not made."
        ),
    },
    "D24": {
        "verdict": "not written",
        "reason": (
            "The conversion was attempted field by field and five REQUIRED "
            "fields have no source anywhere in the build. "
            "`v1/evidence/d24_calibration_targets.json` is produced by "
            "`calibration.targets.build_d24`, whose `CalibrationTarget` "
            "dataclass has eleven fields; eleven of D24's seventeen can be "
            "filled from it and from the source register (see `field_mapping`), "
            "and five cannot. "
            "`domain` is declared as 'population | activity | appliance | "
            "physics | weather | mimic' and the 113 targets on disk are "
            "household electricity, household gas and rental floor area - none "
            "of which is any of those six, so any value would be a "
            "misclassification. `tolerance` is declared float and the "
            "tolerances that exist are PROSE, per plausibility CHECK rather "
            "than per target ('ratio in [0.40, 1.00]', 'between 15 and 125 "
            "litres per person per day', in plausibility/checks.py), so there "
            "is no number to put in it. `tolerance_kind`, `evidence_tag` and "
            "`provisional` appear nowhere. "
            "Separately, D24 is META, so its release package is `v1/evidence/` "
            "- outside the paths this export was permitted to write - which "
            "means even a conformant frame could not be placed."
        ),
        "missing_required": [
            "domain", "tolerance", "tolerance_kind", "evidence_tag",
            "provisional",
        ],
        "field_mapping": {
            "target_id": "artefact target_id, unchanged",
            "statistic": "artefact `quantity`, RENAMED",
            "unit": "artefact unit, unchanged",
            "value": "artefact value, unchanged",
            "value_json": (
                "could carry the artefact's `conditioned_on` dict, for which "
                "the schema declares no column"
            ),
            "source_sha256": "artefact source_sha256, unchanged",
            "source_file": "sources.REGISTRY[source_key].relpath",
            "source_url": "sources.REGISTRY[source_key].url",
            "source_licence": "sources.REGISTRY[source_key].licence",
            "intended_use": "sources.REGISTRY[source_key].intended_use",
            "model_development_exposure": (
                "artefact `exposure`, RENAMED; cross-checkable against "
                "sources.REGISTRY[source_key].model_development_exposure"
            ),
            "retrieved_at": "the source's own per-file manifest, via sources.manifest_for",
            "domain": "NO SOURCE",
            "tolerance": "NO SOURCE as a float",
            "tolerance_kind": "NO SOURCE",
            "evidence_tag": "NO SOURCE",
            "provisional": "NO SOURCE",
        },
        "artefact_keys_the_schema_does_not_declare": [
            "conditioned_on", "scope_note", "source_key", "source_title",
            "year", "quantity (renamed to statistic)",
            "exposure (renamed to model_development_exposure)",
        ],
        "needs": (
            "a decision on three schema questions - what `domain` means for an "
            "energy-consumption target, whether `tolerance` is a float or a "
            "stated band, and where a target's conditioning lives - plus the "
            "generator emitting tolerance_kind, evidence_tag and provisional. "
            "A SCHEMA finding for Appendix D, reported and not edited."
        ),
    },
}
    "D21": {
        "verdict": "not written",
        "reason": (
            "There is no narrative generator in the package. D21 is named only "
            "in release/packages.py, schema/model.py and the catalogue "
            "generator; nothing builds `narrative_md` or the "
            "`source_record_ids` that design 5.2 step 6 requires every "
            "sentence to trace to. Writing prose here would be free-written "
            "text, which is the one thing the field's own note forbids."
        ),
        "missing_required": ["narrative_md", "source_record_ids"],
        "needs": "a new generator (subsystem S04). Not an export concern.",
    },
    "D23": {
        "verdict": "not written",
        "reason": (
            "D23 describes the RUN, and the runs on disk did not record what it "
            "declares. `run_diagnostics.json` carries the master seed, the "
            "coupling mode and the slice, and none of `code_git_sha`, "
            "`code_tree_hash`, `input_sources` with their SHA-256, or "
            "`outputs` path -> SHA-256. `baile_nua.manifest.RunManifest` can "
            "compute all four - but it would compute them for the tree as it "
            "stands NOW, which describes this exporter's commit and not the "
            "commit that produced the package. A provenance record that "
            "misstates its own provenance is worse than its absence."
        ),
        "missing_required": [
            "code_version", "code_git_sha", "code_tree_hash", "input_sources",
            "outputs",
        ],
        "needs": (
            "the runner writing a RunManifest at run time (it already can: "
            "`write_t0` accepts one). For a run already finished, nothing can "
            "recover it honestly."
        ),
    },
    "D27": {
        "verdict": "not written",
        "reason": (
            "There is no tariff or contract model. Nothing in the package "
            "holds a supplier, a tariff code, a rate card, a standing charge "
            "or a connection capacity: `rl.interface` lists "
            "`tariff_import_eur_kwh` as an observation a future RL agent would "
            "see, and `engine.fork` lists `tariff` as a fork KIND, but neither "
            "is a tariff. The only tariff-adjacent declared source is CSO "
            "MEC05, which is metered consumption by tariff GROUP and carries "
            "no rates. Seven of D27's fields are required and none of them has "
            "a value that could be traced to anything."
        ),
        "missing_required": [
            "supplier", "tariff_code", "tariff_kind", "rate_schedule",
            "standing_charge_eur_day", "max_import_kw", "max_export_kw",
        ],
        "needs": (
            "a source acquisition (published Irish retail rate cards and "
            "connection capacities, declared in SOURCES.md before use) plus a "
            "contract model. Appendix D already records this as 'the "
            "edge-export contract view is not written by E1's runner'."
        ),
    },
"""


#: Why a META dataset is absent from an export that was only permitted to
#: write the observable and ground-truth packages.  Not a gap in the exporter:
#: :func:`baile_nua.export.structural.export_d22` writes D22 happily, and
#: :func:`baile_nua.io.write_dataset` correctly refuses to place a META
#: dataset anywhere but ``evidence/``.
EVIDENCE_PACKAGE_NOTE = (
    "META: its release package is <out_root>/evidence/, which this export run "
    "was not permitted to write. The exporter exists and has been exercised "
    "against a scratch out_root; point export_all at an out_root whose "
    "evidence/ directory may be written and it lands there."
)


def reason_for(dataset_id: str) -> dict[str, Any] | None:
    """The recorded reason a dataset is absent, or ``None`` if there is none."""
    if dataset_id in ABSENT:
        return dict(ABSENT[dataset_id])
    if dataset_id in OWNED_ELSEWHERE:
        return {"verdict": "not written",
                "reason": OWNED_ELSEWHERE[dataset_id],
                "missing_required": [], "needs": "nothing: another owner"}
    return None
