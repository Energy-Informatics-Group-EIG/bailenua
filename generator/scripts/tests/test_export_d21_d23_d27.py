"""One schema test per dataset for D21, D23 and D27, plus what each claims.

``test_export_dataset_schemas.py`` already checks all 31 datasets against
``datasets.yaml`` over every export target, and D21, D23 and D27 are picked up
there automatically now that they are written.  This file tests the claims
those three make that a schema check cannot see:

* **D23** - that every declared field carries one of the seven declared
  provenance classes, that the ``-reconstructed`` suffixes go on exactly the
  fields whose class is a reconstruction, and that the row's own evidence about
  why the freeze tag is not the run's code is true of the repository.
* **D21** - that every id in ``source_record_ids`` resolves to a row of the
  dataset it names, that the ids in the column and the ids cited inline in
  ``narrative_md`` are the same set in both directions, and that
  ``cluster_label`` is null.
* **D27** - that **nothing in the engine can read it**, that its RNG stream
  cannot collide with a declared one, that plan assignment is reproducible, and
  that the DEAP clauses quoted as its structural basis are in the PDF's bytes.

Every test skips with a reason when its part is not on disk and never passes
vacuously.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import baile_nua
from baile_nua.export.biographies import PRIMARY_KEY, SOURCE_DATASETS
from baile_nua.export.run_manifest import FREEZE_TAG, PROVENANCE_CLASSES
from baile_nua.export.tariffs import (
    BAND_HOURS,
    DAYS_PER_YEAR,
    DEAP_STRUCTURE_QUOTES,
    EXPORT_RATE_EUR_KWH,
    EXPORT_TARIFF_PLAN_STREAM,
    PLANS,
    RATE_SOURCE_KEYS,
    STRUCTURE_SOURCE_KEYS,
    TARIFF_ASSUMPTIONS,
    TARIFF_RATES,
    plan_for_premises,
    plan_mix,
    price_cross_check,
)
from baile_nua.schema import load

PROJECT_ROOT = Path(baile_nua.__file__).resolve().parents[2]
PACKAGE_ROOT = Path(baile_nua.__file__).resolve().parent

#: ``(name, out_root, subdir)`` - the same targets the schema suite uses.
TARGETS: tuple[tuple[str, Path, str | None], ...] = (
    ("estate-year", PROJECT_ROOT / "v1", None),
    ("town-14day", PROJECT_ROOT / "v1", "town14"),
)


def _parts(out_root: Path, subdir: str | None, dataset_id: str) -> list[Path]:
    from baile_nua.schema.access import package_for

    base = out_root / package_for(dataset_id, load())
    if subdir:
        base = base / subdir
    return sorted(base.glob(f"{dataset_id}_part*.parquet"))


def _read(out_root: Path, subdir: str | None, dataset_id: str):
    import pandas as pd

    parts = _parts(out_root, subdir, dataset_id)
    if not parts:
        pytest.skip(
            f"{dataset_id} has no part under {out_root} (subdir={subdir}); "
            f"run baile_nua.export.export_all for this target first"
        )
    return pd.concat([pq.read_table(p).to_pandas() for p in parts],
                     ignore_index=True)


# --------------------------------------------------------------------------- #
# D23
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d23_every_declared_field_carries_a_declared_provenance_class(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """The whole point of the dataset: no field without a stated provenance."""
    frame = _read(out_root, subdir, "D23")
    declared = set(load()["D23"].field_map)
    for _, row in frame.iterrows():
        prov = json.loads(row["parameters"])["field_provenance"]
        missing = sorted(declared - set(prov))
        assert not missing, (
            f"{target}: D23 field(s) {missing} have no provenance entry. A "
            f"field with no stated provenance is indistinguishable from a "
            f"captured one, which is what this dataset exists to prevent."
        )
        for field, entry in prov.items():
            assert entry["provenance"] in PROVENANCE_CLASSES, (
                f"{target}: D23.{field} has provenance class "
                f"{entry['provenance']!r}, which is not one of "
                f"{PROVENANCE_CLASSES}")
            assert entry.get("evidence"), (
                f"{target}: D23.{field} states a provenance class with no "
                f"evidence for it")


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d23_the_reconstructed_suffix_matches_the_provenance_class(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """A '-reconstructed' suffix on a captured field, or none on a rebuilt one,
    would make the top-level warning disagree with the authority."""
    frame = _read(out_root, subdir, "D23")
    for _, row in frame.iterrows():
        prov = json.loads(row["parameters"])["field_provenance"]
        for field in ("code_git_sha", "code_tree_hash", "code_version"):
            cls = prov[field]["provenance"]
            value = str(row[field])
            if cls == "reconstructed_from_git_history":
                assert "-reconstructed" in value, (
                    f"{target}: D23.{field} is {cls} but its value "
                    f"{value!r} carries no '-reconstructed' marker, so a "
                    f"reader of the column alone would read it as captured")
            elif cls == "captured_at_run_time":
                assert "-reconstructed" not in value, (
                    f"{target}: D23.{field} is captured but its value is "
                    f"marked reconstructed")
        assert str(row["run_id"]).startswith("D23-RECONSTRUCTED-"), (
            f"{target}: run_id {row['run_id']!r} does not announce that this "
            f"is not a manifest the run wrote")
        assert prov["run_id"]["provenance"] == "assigned_by_exporter"


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d23_the_claim_that_the_tag_is_not_the_runs_code_is_true(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """The row's reason for not using the tag's hash, checked against git.

    If this ever fails because the lists agree, the honest response is to
    re-class ``code_tree_hash`` as verified, not to delete the test.
    """
    import subprocess

    frame = _read(out_root, subdir, "D23")
    for _, row in frame.iterrows():
        evidence = json.loads(row["parameters"])["code_state_evidence"]
        if not evidence.get("nearest_commit_at_or_before_run_start"):
            pytest.skip(f"{target}: no git evidence recorded in the row")
        repo = Path(evidence["repo"])
        if not (repo / ".git").exists():
            pytest.skip(f"{target}: {repo} is no longer a git repository")
        out = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only",
             evidence["nearest_commit_at_or_before_run_start"],
             evidence["freeze_tag_sha"], "--", "scripts/baile_nua"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if out.returncode != 0:
            pytest.skip(f"{target}: git is unavailable ({out.stderr.strip()})")
        changed = sorted(
            n for n in out.stdout.splitlines()
            if n and not n.startswith("scripts/tests")
            and Path(n).suffix in (".py", ".yaml", ".yml")
        )
        assert changed == sorted(
            evidence["model_code_files_changed_between_that_commit_and_the_tag"]
        ), (
            f"{target}: the row says {len(evidence['model_code_files_changed_between_that_commit_and_the_tag'])} "
            f"model-code files changed between the run's nearest commit and "
            f"{FREEZE_TAG}; git says {len(changed)}. The row's own reason for "
            f"not using the tag's tree hash must be true of the repository."
        )


# --------------------------------------------------------------------------- #
# D21
# --------------------------------------------------------------------------- #

_CITE = re.compile(r"\[([^\[\]]+)\]")


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d21_every_cited_record_id_resolves_to_a_row(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """Design 5.2 step 6, as a test: every sentence traces to a record.

    An id that resolves to nothing is a narrative making a claim a reader
    cannot check, which is the failure mode the field exists to prevent.
    """
    frame = _read(out_root, subdir, "D21")
    keys: dict[str, set[str]] = {}
    for dataset_id in SOURCE_DATASETS:
        parts = _parts(out_root, subdir, dataset_id)
        if not parts:
            keys[dataset_id] = set()
            continue
        column = PRIMARY_KEY[dataset_id]
        values: set[str] = set()
        for path in parts:
            values.update(
                str(v) for v in
                pq.read_table(path, columns=[column])[column].to_pylist())
        keys[dataset_id] = values

    cited: set[str] = set()
    for ids in frame["source_record_ids"]:
        cited.update(map(str, list(ids)))
    assert cited, f"{target}: D21 cites no record at all"
    for rid in sorted(cited):
        dataset_id, _, key = rid.partition(":")
        assert dataset_id in PRIMARY_KEY, (
            f"{target}: {rid!r} names {dataset_id!r}, which has no declared "
            f"primary key, so the citation cannot be resolved")
        assert key in keys[dataset_id], (
            f"{target}: {rid!r} is cited by a biography but "
            f"{PRIMARY_KEY[dataset_id]}={key!r} is not a row of the written "
            f"{dataset_id}. A citation that resolves to nothing is worse than "
            f"no citation.")


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d21_the_column_and_the_narrative_cite_the_same_records(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """Both directions: no id in the column that no sentence used, and no
    sentence citing an id the column does not carry."""
    frame = _read(out_root, subdir, "D21")
    for _, row in frame.iterrows():
        declared = set(map(str, list(row["source_record_ids"])))
        inline: set[str] = set()
        for block in _CITE.findall(row["narrative_md"]):
            for piece in block.split(";"):
                piece = piece.strip()
                if piece.partition(":")[0] in PRIMARY_KEY:
                    inline.add(piece)
        assert inline == declared, (
            f"{target}/{row['person_id']}/{row['as_of']}: the narrative cites "
            f"{sorted(inline - declared)} that the column omits and the "
            f"column carries {sorted(declared - inline)} that no sentence "
            f"cites. The Markdown is self-citing on purpose, so the two must "
            f"agree.")


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d21_no_person_is_labelled_by_cluster(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """``cluster_label`` is declared forbidden (design 5.13)."""
    frame = _read(out_root, subdir, "D21")
    assert frame["cluster_label"].isna().all(), (
        f"{target}: D21.cluster_label is not always null")


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d21_every_sentence_in_the_markdown_carries_a_citation(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """A bullet with no bracketed id would be a free-written sentence."""
    frame = _read(out_root, subdir, "D21")
    for _, row in frame.iterrows():
        for line in row["narrative_md"].splitlines():
            if not line.startswith("- "):
                continue
            ids = [
                piece.strip()
                for block in _CITE.findall(line)
                for piece in block.split(";")
                if piece.strip().partition(":")[0] in PRIMARY_KEY
            ]
            assert ids, (
                f"{target}/{row['person_id']}: the sentence {line!r} cites no "
                f"record. Every sentence traces to a record (5.2 step 6).")


# --------------------------------------------------------------------------- #
# D27 - the record-only claim
# --------------------------------------------------------------------------- #

#: The layers that must not be able to see a price.
_ENGINE_DIRS: tuple[str, ...] = (
    "engine", "physics", "devices", "behaviour", "activity", "observation",
    "population", "lifecourse",
)


def test_d27_the_engine_cannot_read_the_tariff() -> None:
    """RECORD ONLY, proven over the source tree rather than asserted.

    D27's whole premise is that it is an output and never an input. A single
    import of ``baile_nua.export.tariffs`` from the engine would make the rate
    card a model parameter and the frozen physics a function of a synthetic
    price. So the check is a grep over the layers, not a promise in a
    docstring.
    """
    offenders: dict[str, list[str]] = {}
    for name in _ENGINE_DIRS:
        root = PACKAGE_ROOT / name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            hits = [
                needle for needle in
                ("export.tariffs", "export import tariffs", "from baile_nua.export")
                if needle in text
            ]
            if hits:
                offenders[str(path.relative_to(PACKAGE_ROOT))] = hits
    assert not offenders, (
        f"these modules reference the export layer: {offenders}. D27 is a "
        f"record only; the engine must not be able to read a tariff, and "
        f"nothing in the frozen layers may import baile_nua.export at all."
    )


def test_d27_no_frozen_layer_names_the_rate_card() -> None:
    """Not even by string: no tariff code, supplier or rate constant."""
    needles = (
        "BN-SYNTH", "Baile Nua Synthetic Supply",
        "standing_charge_eur_day", "export_rate_eur_kwh", "rate_schedule",
    )
    offenders: dict[str, list[str]] = {}
    for name in _ENGINE_DIRS:
        root = PACKAGE_ROOT / name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            hits = [n for n in needles if n in text]
            if hits:
                offenders[str(path.relative_to(PACKAGE_ROOT))] = hits
    assert not offenders, (
        f"these frozen modules name a D27 field or the rate card: "
        f"{offenders}. A frozen layer that reads a tariff field by name is "
        f"reading the tariff."
    )


def test_d27_the_export_stream_cannot_collide_with_a_declared_one() -> None:
    """A stream id shared with a declared subsystem is a shared sequence."""
    from baile_nua.rng import Stream

    declared = {int(s): s.name for s in Stream}
    assert EXPORT_TARIFF_PLAN_STREAM not in declared, (
        f"stream {EXPORT_TARIFF_PLAN_STREAM} is declared in rng.Stream as "
        f"{declared.get(EXPORT_TARIFF_PLAN_STREAM)}; the export layer must "
        f"not borrow a production or test stream")
    assert EXPORT_TARIFF_PLAN_STREAM > max(declared), (
        f"stream {EXPORT_TARIFF_PLAN_STREAM} is below the highest declared "
        f"Stream value {max(declared)}, so appending to the enum could reach "
        f"it. The export range must sit clear of it.")


def test_d27_plan_assignment_is_reproducible_and_seed_dependent() -> None:
    """Counter-based, so the same premises gets the same plan on a re-run."""
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)

    weights = plan_mix()["weights"]
    premises = [f"MPRN-{i:08X}" for i in range(400)]
    first = [plan_for_premises(p, 20261008, weights) for p in premises]
    second = [plan_for_premises(p, 20261008, weights) for p in premises]
    assert first == second, "plan assignment is not reproducible"
    assert set(first) <= set(PLANS)
    other = [plan_for_premises(p, 20251010, weights) for p in premises]
    assert other != first, (
        "a different master seed produced an identical assignment, so the "
        "draw is not keyed by the seed")
    assert len(set(first)) == len(PLANS), (
        f"only {sorted(set(first))} of {sorted(PLANS)} were drawn over 400 "
        f"premises, so the draw does not reach every plan")


def test_d27_the_plan_mix_is_the_published_urban_share() -> None:
    """The mix is read from HEBEU88, renormalised, and nothing is reassigned."""
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)

    mix = plan_mix()
    assert set(mix["weights"]) == set(PLANS)
    assert abs(sum(mix["weights"].values()) - 1.0) < 1e-9
    published = mix["published_urban_shares_pct"]
    # The three categories the plans map onto must each be published, and the
    # ones they do not map onto must be REPORTED rather than folded in.
    for plan in PLANS.values():
        assert plan["hebeu88_category"] in published
    assert mix["unassigned_pct"], (
        "HEBEU88's 'Other tariff NEC' and 'Tariff type unknown' shares must be "
        "reported; silently folding them into a plan would turn a non-answer "
        "into evidence for a tariff")
    # The largest published share must be the largest weight: a renormalisation
    # that reordered the categories would be a bug.
    by_weight = max(mix["weights"], key=lambda c: mix["weights"][c])
    assigned = {
        p["hebeu88_category"]: code for code, p in PLANS.items()}
    by_published = assigned[max(
        (c for c in assigned if published.get(c) is not None),
        key=lambda c: published[c])]
    assert by_weight == by_published


def test_d27_the_published_price_series_brackets_the_card() -> None:
    """CSO TMEGB03 against the supplier schedule the card carries.

    An independent check: the CSO publishes the series and the supplier
    publishes the schedule. If this fails, the finding is reported - the card
    is NOT adjusted to make it pass, because the card carries what was
    published.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)

    check = price_cross_check()
    assert check["published_2022_eur_kwh_by_semester"], (
        "TMEGB03 carries no 2022 band-DC price, so the level is unchecked")
    assert check["within_the_published_semesters"], (
        f"the card's flat rate {check['card_flat_rate_eur_kwh']} is outside "
        f"the CSO's published 2022 band-DC prices "
        f"{check['published_2022_eur_kwh_by_semester']}. Report it; do not "
        f"move the card, which carries the published schedule.")


def test_d27_every_sourced_rate_names_a_declared_fetched_source() -> None:
    """No magnitude without a declared source, a page and a quote."""
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import REGISTRY, manifest_for

    assert TARIFF_RATES, "the module carries no sourced rates"
    for name, value in sorted(TARIFF_RATES.items()):
        assert value.source_key in REGISTRY, (
            f"{name} cites {value.source_key}, which is not declared in "
            f"sources_registry.py")
        src = REGISTRY[value.source_key]
        assert manifest_for(src) is not None, (
            f"{name} cites {value.source_key}, which has no manifest: it was "
            f"declared but never fetched, and an unfetched source proves "
            f"nothing")
        assert src.model_development_exposure == "none", (
            f"{value.source_key} is exposure "
            f"{src.model_development_exposure!r}; a record-only tariff source "
            f"must be 'none'")
        assert value.quote.strip(), f"{name} cites no published wording"
        assert value.page is not None or value.source_key.startswith("cso."), (
            f"{name} cites a PDF with no page")
    for key in RATE_SOURCE_KEYS + STRUCTURE_SOURCE_KEYS:
        assert key in REGISTRY, f"{key} is not declared"


def test_d27_the_standing_charge_is_the_published_annual_over_365() -> None:
    """A derivation stated on the dataset, checked here."""
    for code, plan in PLANS.items():
        annual = TARIFF_RATES[plan["standing_charge_key"]].value
        expected = round(annual / DAYS_PER_YEAR, 6)
        assert expected > 0, f"{code} has no standing charge"
        assert abs(expected - annual / 365.0) < 1e-6


def test_d27_the_export_rate_is_the_midpoint_of_the_published_range() -> None:
    """A stated rule, not a chosen number."""
    low = TARIFF_RATES["export_range_low_eur_kwh"].value
    high = TARIFF_RATES["export_range_high_eur_kwh"].value
    assert low < high
    assert abs(EXPORT_RATE_EUR_KWH - (low + high) / 2.0) < 1e-9
    assert TARIFF_RATES["export_floor_eur_kwh"].value == 0.0, (
        "the CRU's regulated floor is zero; if that changed, the card's "
        "evidence changed with it")


def test_d27_every_sourced_rate_is_in_its_cited_document() -> None:
    """The transcription, checked against the fetched bytes.

    Five of the rate sources are PDFs, which the project's rule requires be
    transcribed by hand with page and wording. This is the check that makes
    that rule worth anything: a mistyped figure fails here instead of being
    published as a citation.

    Compared with ALL whitespace removed, because the published PDFs' own text
    layer carries stray spaces inside numbers - the NightSaver standing charge
    extracts as 'EUR 327 .04'.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import SourceError, require

    pypdf = pytest.importorskip("pypdf")
    cited = [
        (name, v) for name, v in sorted(TARIFF_RATES.items())
        if v.page is not None
    ] + [(f"band_hours.{k}", v) for k, v in sorted(BAND_HOURS.items())]
    assert cited, "no PDF-sourced figure is cited at all"
    readers: dict[str, object] = {}
    for name, value in cited:
        try:
            path = require(value.source_key)
        except SourceError as exc:
            pytest.skip(f"{value.source_key} is not on disk: {exc}")
        if value.source_key not in readers:
            readers[value.source_key] = pypdf.PdfReader(str(path))
        reader = readers[value.source_key]
        page = reader.pages[int(value.page) - 1]
        haystack = re.sub(r"\s+", "", page.extract_text() or "")
        needle = re.sub(r"\s+", "", value.quote)
        assert needle in haystack, (
            f"{name}: the wording {value.quote!r} is not on page "
            f"{value.page} of {value.source_key}. Either the transcription is "
            f"wrong or the published document moved; fix the citation, do not "
            f"drop the check."
        )


@pytest.mark.parametrize(("target", "out_root", "subdir"), TARGETS,
                         ids=[t[0] for t in TARGETS])
def test_d27_is_labelled_synthetic_on_its_face(
    target: str, out_root: Path, subdir: str | None,
) -> None:
    """The card says what it is in its own rows, not only in a manifest."""
    frame = _read(out_root, subdir, "D27")
    assert frame["supplier"].str.contains("SYNTHETIC").all(), (
        f"{target}: a D27 row's supplier is not marked synthetic")
    for _, row in frame.iterrows():
        card = json.loads(row["rate_schedule"])
        assert "SYNTHETIC" in card["label"]
        assert "UNVALIDATED SIMULATION EVIDENCE" in card["label"]
        assert card["structure_source_keys"], (
            f"{target}: the card names no declared source for its structure")
        assert card["rate_source_keys"], (
            f"{target}: the card names no declared source for its rates")
        # Every band's rate carries the source it was read from, and the row's
        # own scalar fields agree with the card.
        for band in card["bands"]:
            assert band["rate_source"]["source_key"], (
                f"{target}: a band rate cites no source")
            assert band["rate_source"]["quoted"], (
                f"{target}: a band rate cites no published wording")
        assert abs(
            card["standing_charge_eur_day"]
            - float(row["standing_charge_eur_day"])) < 1e-9, (
            f"{target}: the card and the column disagree on the standing "
            f"charge")
        assert abs(
            card["export_rate_eur_kwh"]
            - float(row["export_rate_eur_kwh"])) < 1e-9
        assert card["rate_schedule_vintage"], (
            f"{target}: the card does not say which schedule it is from")


def test_d27_every_magnitude_has_a_flag_with_a_search_record() -> None:
    """An assumption with no search record is the I-040 failure repeating.

    Retired flags are kept and still checked: a RETIRED verdict has to name a
    source that is declared AND fetched, or it is an assertion rather than a
    retirement.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import REGISTRY, manifest_for

    assert TARIFF_ASSUMPTIONS, "the tariff module declares no assumptions"
    subjects = " | ".join(f.subject.lower() for f in TARIFF_ASSUMPTIONS)
    for word in ("rate magnitudes", "plan mix", "band boundaries",
                 "standing charge", "export rate", "maximum import",
                 "vintage"):
        assert word in subjects, (
            f"no flag covers {word!r}, so that magnitude is unaccounted for")
    for flag in TARIFF_ASSUMPTIONS:
        assert flag.search_terms, f"{flag.flag_id} records no search"
        assert flag.retires_if, f"{flag.flag_id} says nothing would retire it"
        assert flag.verdict_note, f"{flag.flag_id} declares a verdict with no note"
        if flag.verdict in ("RETIRED", "SOURCE_FOUND"):
            assert flag.sources and flag.owning_step
            for key in flag.sources:
                assert key in REGISTRY, (
                    f"{flag.flag_id} names {key}, which is not declared")
                assert manifest_for(REGISTRY[key]) is not None, (
                    f"{flag.flag_id} is {flag.verdict} on {key}, which was "
                    f"declared but never fetched. An unfetched source proves "
                    f"nothing.")


def test_d27_the_searches_still_find_the_tables_the_verdicts_rest_on() -> None:
    """The verdicts, run against the declared catalogue rather than asserted.

    Two retirements rest on PxStat tables, and A-92's standing claim is that
    PxStat carries no meter band window at all. Both directions are checked, so
    neither can go stale when the CSO publishes something.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    try:
        catalogue = load_catalogue()
    except Exception as exc:                        # the source must be present
        pytest.skip(f"the PxStat catalogue source is not available: {exc}")
    by_id = {f.flag_id: f for f in TARIFF_ASSUMPTIONS}

    prices = {h.matrix for h in search(r"electricity price", catalogue)}
    assert "TMEGB03" in prices, (
        "A-90's level check rests on TMEGB03 'Residential Electricity Prices' "
        "and the search no longer finds it in the catalogue")
    tariffs_found = {h.matrix for h in search(r"tariff", catalogue)}
    assert {"HEBEU85", "HEBEU88"} <= tariffs_found, (
        "A-91 is retired on HEBEU88's published tariff-type dimension and the "
        "search no longer finds it")

    # A-92 still stands, and it stands on a negative result: PxStat publishes
    # no meter band window. Good news if this fails - the flag can be retired.
    a92 = by_id["A-92"]
    assert a92.verdict == "KEPT"
    for term in (r"night rate", r"night saver", r"day/night"):
        assert term in a92.search_terms
        hits = search(term, catalogue)
        assert not hits, (
            f"A-92 claims PxStat carries no night-rate band window, but "
            f"{term!r} now matches {len(hits)} tables, e.g. "
            f"{[(h.matrix, h.title) for h in hits[:3]]}. If one publishes the "
            f"hours, the flag can be retired.")


def test_d27_the_deap_structure_quotes_are_in_the_pdf() -> None:
    """The card's structural basis, checked against the declared bytes.

    The quotes are transcribed into this package by hand, which is the one
    thing the DEAP source's own manifest flags about it ("PDF, not
    machine-readable"). So they are checked against the file rather than
    trusted, and a transcription error is a failure here rather than a false
    citation in a published dataset.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import SourceError, require

    pypdf = pytest.importorskip("pypdf")
    try:
        path = require("seai.deap.manual_4_2_7")
    except SourceError as exc:
        pytest.skip(f"the DEAP manual is not on disk: {exc}")
    reader = pypdf.PdfReader(str(path))
    for item in DEAP_STRUCTURE_QUOTES:
        page = reader.pages[int(item["page"]) - 1]
        text = re.sub(r"\s+", " ", page.extract_text() or "")
        needle = re.sub(r"\s+", " ", item["quote"])
        assert needle in text, (
            f"the quote {needle!r} is not on page {item['page']} of "
            f"{path.name}. Either the transcription is wrong or the source "
            f"moved; fix the citation, do not drop the check."
        )
