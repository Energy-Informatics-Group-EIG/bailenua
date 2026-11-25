"""Tests for ``scripts/gen_provenance.py``.

The generator's job is to make claims about provenance, so the tests are about
the two ways such a page goes wrong: claiming a source that is not there, and
quietly failing to claim one that is.  The second is the harder one and is why
:func:`test_the_scan_actually_finds_sources` and
:func:`test_every_subsystem_in_the_schema_is_mapped` exist - a scan that
silently matches nothing would make every cell read "no source" and the page
would look tidy and say nothing.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gen_provenance as gp  # noqa: E402


@pytest.fixture(scope="module")
def prov() -> gp.Provenance:
    return gp.Provenance()


@pytest.fixture(scope="module")
def rows(prov: gp.Provenance) -> list[gp.DatasetRow]:
    return prov.rows()


# --------------------------------------------------------------------------- #
# coverage of the declared datasets
# --------------------------------------------------------------------------- #

def test_one_row_per_declared_dataset(prov, rows):
    from baile_nua.export.dispatch import ALL_DATASETS

    assert [r.dataset_id for r in rows] == list(ALL_DATASETS)
    assert len(rows) == 32, "31 declared datasets plus D17_aggregate"


def test_d17_aggregate_is_present_and_is_not_d17(rows):
    """I-099: two reporting paths filed D17's observable view under D17."""
    by_id = {r.dataset_id for r in rows}
    assert {"D17", "D17_aggregate"} <= by_id
    rows_by_id = {r.dataset_id: r for r in rows}
    assert rows_by_id["D17"].access_class == "GT"
    assert rows_by_id["D17_aggregate"].access_class == "OBS"


def test_every_subsystem_in_the_schema_is_mapped(prov):
    """An unmapped subsystem would silently contribute no builder modules."""
    assert gp.check_subsystem_map(prov) == []


def test_every_row_has_a_title_from_the_schema(prov, rows):
    declared = prov.schema["datasets"]
    for row in rows:
        assert row.title == str(declared[row.dataset_id]["title"])


# --------------------------------------------------------------------------- #
# the source scan
# --------------------------------------------------------------------------- #

def test_the_scan_actually_finds_sources(prov):
    """A guard that silently matches nothing is worse than no guard."""
    found = {
        key
        for module in prov.texts
        if not module.startswith("sources")
        for key in prov.keys_loaded_by(module)
    }
    assert len(found) > 30, (
        f"only {len(found)} of {len(prov.registry)} declared keys were found "
        f"to be loaded by any module; the load patterns have stopped matching"
    )


def test_the_weather_station_keys_are_found(prov):
    """`weather/station.py` holds its key in a StationSpec, not a require()."""
    keys = prov.keys_loaded_by("weather/station.py")
    assert "met.cork_airport.hourly" in keys
    assert "met.roches_point.hourly" in keys


def test_both_babynames_tables_are_found(prov):
    """`population/names.py` picks one in a ternary; both must be seen."""
    keys = prov.keys_loaded_by("population/names.py")
    assert {"cso.babynames.boys", "cso.babynames.girls"} <= set(keys)


def test_a_path_literal_under_sources_is_a_citation(prov):
    """`engine/calendar.py` reads two tables by path, bypassing the registry."""
    paths = prov.paths_cited_by("engine/calendar.py")
    assert "sources/derived/school_breaks.csv" in paths
    assert "sources/derived/irish_public_holidays_2014_2026.csv" in paths


def test_the_run_manifest_cites_the_whole_register(prov, rows):
    """D23 records every declared input, so it must cite the register."""
    assert prov.reads_whole_register("export/run_manifest.py")
    d23 = next(r for r in rows if r.dataset_id == "D23")
    assert any(c.kind == "corpus" for c in d23.citations)


# --------------------------------------------------------------------------- #
# attribution breadth
# --------------------------------------------------------------------------- #

def test_the_dispatcher_is_not_a_builder(prov):
    """`export/dispatch.py` names 27 datasets and builds none of them."""
    assert prov.names_count["export/dispatch.py"] > gp.PLUMBING_LIMIT
    assert "export/dispatch.py" not in prov.naming_modules("D16")


def test_a_scoring_module_is_never_a_builder(prov):
    """A source a scoring module reads is one the dataset is compared against."""
    for dataset_id in prov.dataset_ids:
        for module in prov.builders_for(dataset_id):
            assert module.split("/")[0] not in gp.SCORING_PACKAGES, (
                f"{module} is a scoring module and was attributed to "
                f"{dataset_id} as a builder"
            )


def test_the_producer_is_always_a_builder(prov):
    from baile_nua.export.dispatch import EXPORTERS

    for dataset_id, fn in EXPORTERS.items():
        rel = fn.__module__[len("baile_nua."):].replace(".", "/") + ".py"
        assert rel in prov.builders_for(dataset_id)


# --------------------------------------------------------------------------- #
# the transform column
# --------------------------------------------------------------------------- #

def test_an_exported_dataset_names_its_exporter(prov):
    assert "baile_nua.export.structural.export_d01" in prov.transform_for("D01")
    assert "baile_nua.export.tariffs.export_d27" in prov.transform_for("D27")


def test_an_engine_streamed_dataset_names_a_stream_writer_method(prov):
    assert prov.stream_writer_methods("D10") == ["add_day"]
    assert prov.stream_writer_methods("D17") == ["add_network_day"]
    assert prov.stream_writer_methods("D17_aggregate") == ["add_network_day"]
    assert any(
        "StreamWriter.add_network_day" in t
        for t in prov.transform_for("D17_aggregate")
    )


def test_a_relocated_dataset_says_where_it_lands(prov):
    """I-091 / I-103: D03, D09 and D20 are the WP5 decade's rows."""
    for dataset_id in ("D03", "D09", "D20"):
        assert any(
            "wp5_decade" in t for t in prov.transform_for(dataset_id)
        ), dataset_id


def test_a_dataset_nothing_writes_names_no_transform(prov, rows):
    """Inventing a writer would lie - but WHICH datasets lack one is read
    from the registry, not listed here.

    As first written this hardcoded D04, D12 and D24. That was true on the day
    and false a few hours later: agent D added exporters for D04 and D24, so
    the generator correctly began reporting a transform for them and this test
    failed for being out of date rather than for anything being wrong. A
    hand-written list of absences rots exactly the way the hand-written list of
    negative controls did, which is the lesson `assumption_sweep.uncovered_files`
    was built around. So the set comes from `dispatch.ABSENT`.
    """
    from baile_nua.export.dispatch import ABSENT, EXPORTERS

    by_id = {r.dataset_id: r for r in rows}
    assert ABSENT, "if nothing is absent this test has no subject left"
    for dataset_id in sorted(ABSENT):
        assert dataset_id in by_id, dataset_id
        assert by_id[dataset_id].transform == [], dataset_id
        assert by_id[dataset_id].status == "not written", dataset_id

    # The converse, so this cannot pass by the registry simply going empty:
    # anything with an exporter must NAME it.
    for dataset_id in sorted(set(EXPORTERS) & set(by_id)):
        assert by_id[dataset_id].transform != [], (
            f"{dataset_id} has an exporter but the page names no transform")


# --------------------------------------------------------------------------- #
# status and defects
# --------------------------------------------------------------------------- #

def test_the_replays_omission_is_reported(prov, rows):
    """D18 is omitted by `scripts/replay_config.json`; the page must say so."""
    assert "D18" in prov.omitted
    d18 = next(r for r in rows if r.dataset_id == "D18")
    assert "omitted" in d18.status
    assert any("OMITTED" in n for n in d18.notes)


def test_d15_carries_the_i111_correction(rows):
    """I-111: D15's `is_dst` column was inverted and is corrected, not shipped."""
    d15 = next(r for r in rows if r.dataset_id == "D15")
    text = " ".join(d15.defects)
    assert "I-111" in text
    assert "is_dst" in text
    assert "CORRECTED" in text or "corrected" in text


def test_d14_carries_the_i110_correction(rows):
    d14 = next(r for r in rows if r.dataset_id == "D14")
    assert any("I-110" in d for d in d14.defects)


def test_issues_are_attached_from_the_log_by_heading(prov):
    """The scan is narrow on purpose; it must still find something."""
    assert prov.issues, "no issue in docs/ISSUES.md names a dataset in its heading"
    # I-099's heading names D17; I-102's names D17_aggregate. Attribution is by
    # the heading, so each lands where its heading points and nowhere else.
    assert any(i.startswith("I-099") for i in prov.issues.get("D17", []))
    assert any(
        i.startswith("I-102") for i in prov.issues.get("D17_aggregate", [])
    )
    # And the status is carried, not just the id.
    assert "OPEN" in " ".join(prov.issues["D17_aggregate"])


# --------------------------------------------------------------------------- #
# assumptions
# --------------------------------------------------------------------------- #

def test_every_assumption_in_a_row_is_declared(prov, rows):
    declared = {f.flag_id for f in prov.flags}
    for row in rows:
        unknown = set(row.assumptions) - declared
        assert not unknown, f"{row.dataset_id} names undeclared {unknown}"


def test_both_assumption_registries_are_loaded(prov):
    ids = {f.flag_id for f in prov.flags}
    assert "A-01" in ids, "validation.assumption_sweep.ASSUMPTION_FLAGS"
    assert "A-92" in ids, "export.tariffs.TARIFF_ASSUMPTIONS"
    assert len(prov.flags) == 64, "56 sweep flags plus 8 tariff flags"


def test_tariff_assumptions_reach_d27(rows):
    d27 = next(r for r in rows if r.dataset_id == "D27")
    assert {"A-90", "A-92", "A-96", "A-97"} <= set(d27.assumptions)


# --------------------------------------------------------------------------- #
# resolution and the UNSOURCED marking
# --------------------------------------------------------------------------- #

def _write_manifest(path: pathlib.Path, **extra) -> None:
    doc = {
        "key": "x.y", "title": "T", "publisher": "P", "licence": "L",
        "sha256": "0" * 64, "retrieved_at": "2026-01-01",
    }
    doc.update(extra)
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_load_manifests_reads_both_shapes(tmp_path):
    sources = tmp_path / "sources"
    (sources / "a").mkdir(parents=True)
    (sources / "a" / "one.csv").write_text("x", encoding="utf-8")
    _write_manifest(sources / "a" / "one.csv.manifest.json",
                    key="k.one", relpath="a/one.csv")
    (sources / "a" / "two.csv").write_text("x", encoding="utf-8")
    # The hand-written shape: no relpath, `fetched_utc` rather than retrieved.
    (sources / "a" / "two.csv.manifest.json").write_text(json.dumps({
        "key": "k.two", "title": "T2", "publisher": "P2", "licence": "L2",
        "sha256": "1" * 64, "fetched_utc": "2026-02-02",
    }), encoding="utf-8")

    got = gp.load_manifests(sources)
    assert set(got) == {"a/one.csv", "a/two.csv"}
    assert got["a/one.csv"].retrieved == "2026-01-01"
    assert got["a/two.csv"].retrieved == "2026-02-02"
    assert got["a/two.csv"].relpath == "a/two.csv"
    assert all(m.resolves for m in got.values())


def test_a_manifest_without_its_bytes_does_not_resolve(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir(parents=True)
    _write_manifest(sources / "gone.csv.manifest.json", relpath="gone.csv")
    got = gp.load_manifests(sources)
    assert got["gone.csv"].file_exists is False
    assert got["gone.csv"].resolves is False


def test_a_file_without_a_manifest_is_unsourced(prov):
    """The real one: the derived holiday table has no manifest beside it."""
    citation = prov._resolve(
        "path", "sources/derived/irish_public_holidays_2014_2026.csv", "t")
    assert not citation.resolved
    assert "no manifest" in citation.unresolved_reason
    cell = gp.render_source_cell([citation])
    assert gp.UNSOURCED in cell


def test_an_unknown_key_is_unsourced(prov):
    citation = prov._resolve("key", "nobody.declares.this", "t")
    assert not citation.resolved
    assert gp.UNSOURCED in gp.render_source_cell([citation])


def test_a_resolved_citation_is_not_marked_unsourced(prov):
    citation = prov._resolve("key", "cso.saps2022.small_area", "t")
    assert citation.resolved
    cell = gp.render_source_cell([citation])
    assert gp.UNSOURCED not in cell
    assert "Central Statistics Office" in cell


def test_the_unsourced_marker_is_inline_html_red(prov):
    """Markdown has no colour; the spec asks for red, so it must be a span."""
    assert gp.UNSOURCED == '<span style="color:red">UNSOURCED</span>'


def test_the_one_unsourced_citation_today_is_the_holiday_table(rows):
    """Honest marking: exactly the citations that do not resolve, no more."""
    unresolved = {
        c.ref for row in rows for c in row.citations if not c.resolved
    }
    assert unresolved == {"sources/derived/irish_public_holidays_2014_2026.csv"}


def test_an_untracked_manifest_resolves_and_says_so(prov):
    """The 7 Phase 0 manifests are on disk and not committed. Said, not hidden."""
    untracked = [m for m in prov.manifests.values() if not m.manifest_tracked]
    if not untracked:
        pytest.skip("every manifest under sources/ is committed in this tree")
    assert all(m.resolves for m in untracked)
    citation = gp.Citation("key", untracked[0].key or "x", "t", untracked[0])
    assert "not committed" in gp.render_source_cell([citation])


# --------------------------------------------------------------------------- #
# the page
# --------------------------------------------------------------------------- #

def test_the_page_renders_one_table_row_per_dataset(prov, rows):
    page = gp.render(prov, rows)
    found = re.findall(r"^\| \*\*(D\d{2}(?:_aggregate)?)\*\*", page, re.M)
    assert found == [r.dataset_id for r in rows]


def test_the_page_states_what_it_does_not_claim(prov, rows):
    """A page that hid its own inference would be the worse artefact."""
    page = gp.render(prov, rows)
    assert "no dataset-to-source mapping" in page
    assert "over-claims" in page or "over-claim" in page


def test_the_page_publishes_a_digest_for_every_resolved_citation(prov, rows):
    page = gp.render(prov, rows)
    for row in rows:
        for c in row.citations:
            if c.resolved and c.manifest is not None:
                assert c.manifest.sha256 in page, c.ref


def test_a_pipe_in_a_cell_cannot_break_the_table():
    assert gp._esc("a | b") == "a \\| b"
    assert "\n" not in gp._esc("a\nb")
