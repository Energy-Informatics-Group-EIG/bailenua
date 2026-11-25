"""Tests for ``scripts/validate_provenance.py``.

The validator exists to fail, so most of these tests feed it a page that is
wrong on exactly one point and assert that it says so.  The two that matter
most are the ones about not failing silently:
:func:`test_an_empty_page_is_unrun_not_a_pass` and
:func:`test_a_missing_page_is_unrun_not_a_pass` - a validator that reports
"no findings" because it parsed nothing is worse than no validator.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_provenance as vp  # noqa: E402
from gen_provenance import CORPUS_REF, UNSOURCED  # noqa: E402

SHA_A = "a" * 64
SHA_B = "b" * 64


def make_page(
    *,
    sources_cell: str = "`cso.saps2022.small_area` — CSO — CC-BY",
    assumptions: str = "A-01, A-10",
    digest_rows: str = f"| `cso.saps2022.small_area` | yes | CSO | CC-BY | `{SHA_A}` | 2026-01-01 |",
    role_rows: str = "",
) -> str:
    return "\n".join([
        "# page",
        "",
        "| Dataset | What it is | Upstream sources | Transform | Assumptions |",
        "|---|---|---|---|---|",
        f"| **D05** | persons | {sources_cell} | `x.y` | {assumptions} |",
        "",
        "| Source | Resolves | Publisher | Licence | SHA-256 | Retrieved |",
        "|---|---|---|---|---|---|",
        digest_rows,
        "",
        "| Source | Role | Read by |",
        "|---|---|---|",
        role_rows or "| — | — | — |",
        "",
    ])


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

def test_parse_recovers_datasets_sources_assumptions_and_digests():
    page = vp.parse_page(make_page())
    assert page.cited == {"D05": ["cso.saps2022.small_area"]}
    assert page.assumptions == {"D05": ["A-01", "A-10"]}
    assert page.digests == {"cso.saps2022.small_area": SHA_A}
    assert page.unsourced == []


def test_a_module_name_in_backticks_is_not_read_as_a_source():
    """`sources_registry.py` matches the key shape and is not a source."""
    assert not vp._is_citation("sources_registry.py")
    assert not vp._is_citation("schema/datasets.yaml")
    assert vp._is_citation("cso.saps2022.small_area")
    assert vp._is_citation("sources/derived/x.csv")
    assert vp._is_citation(CORPUS_REF)


def test_a_path_citation_and_an_unsourced_row_are_recognised():
    page = vp.parse_page(make_page(
        sources_cell="`sources/derived/x.csv` — " + UNSOURCED,
        digest_rows=f"| `sources/derived/x.csv` | {UNSOURCED} — no manifest | — | — | — | — |",
    ))
    assert page.cited["D05"] == ["sources/derived/x.csv"]
    assert page.unsourced == ["sources/derived/x.csv"]
    assert page.digests == {}


def test_the_roles_table_is_parsed():
    page = vp.parse_page(make_page(
        role_rows="| `cso.saps2022.bua` | `read-by-nothing` | — nothing |",
    ))
    assert page.roles == {"cso.saps2022.bua": "read-by-nothing"}


def test_the_corpus_citation_is_recognised():
    page = vp.parse_page(make_page(
        sources_cell=f"`{CORPUS_REF}` — every declared source",
    ))
    assert page.cites_whole_register is True


# --------------------------------------------------------------------------- #
# D23
# --------------------------------------------------------------------------- #

def _d23(sources: dict[str, str]) -> dict:
    return {
        "run_ids": ["r"], "path": "p",
        "sources": {k: {"sha256": v, "relpath": k} for k, v in sources.items()},
    }


def test_a_digest_mismatch_is_reported():
    page = vp.parse_page(make_page())
    found = vp.check_d23_digests(page, _d23({"cso.saps2022.small_area": SHA_B}))
    assert [f.kind for f in found] == ["mismatch"]


def test_a_matching_digest_is_silent():
    page = vp.parse_page(make_page())
    assert vp.check_d23_digests(page, _d23({"cso.saps2022.small_area": SHA_A})) == []


def test_a_source_d23_does_not_record_is_reported():
    page = vp.parse_page(make_page())
    found = vp.check_d23_digests(page, _d23({"something.else": SHA_A}))
    assert [f.kind for f in found] == ["not-recorded"]


def test_a_cited_source_with_no_published_digest_is_reported():
    page = vp.parse_page(make_page(digest_rows="| — | — | — | — | — | — |"))
    found = vp.check_d23_digests(page, _d23({"cso.saps2022.small_area": SHA_A}))
    assert [f.kind for f in found] == ["no-page-digest"]


def test_a_scoring_only_role_closes_the_coverage_check():
    page = vp.parse_page(make_page(
        role_rows="| `cso.energy.sei01_energy_balance` | `scoring-only` | `plausibility/checks.py` |",
    ))
    d23 = _d23({
        "cso.saps2022.small_area": SHA_A,
        "cso.energy.sei01_energy_balance": SHA_B,
    })
    assert vp.check_d23_coverage(page, d23) == []


def test_read_by_nothing_does_not_close_the_coverage_check():
    page = vp.parse_page(make_page(
        role_rows="| `cso.saps2022.bua` | `read-by-nothing` | — nothing |",
    ))
    d23 = _d23({"cso.saps2022.small_area": SHA_A, "cso.saps2022.bua": SHA_B})
    found = vp.check_d23_coverage(page, d23)
    assert [f.kind for f in found] == ["read-by-nothing"]


def test_silence_about_a_d23_source_is_reported_as_unaccounted():
    page = vp.parse_page(make_page())
    d23 = _d23({"cso.saps2022.small_area": SHA_A, "never.mentioned": SHA_B})
    found = vp.check_d23_coverage(page, d23)
    assert [(f.kind, f.subject) for f in found] == [
        ("unaccounted", "never.mentioned")
    ]


def test_citing_the_whole_register_does_not_close_the_coverage_check():
    """It is a fact about D23, not a substitute for 69 answers."""
    page = vp.parse_page(make_page(
        sources_cell=f"`{CORPUS_REF}` — every declared source",
    ))
    assert page.cites_whole_register
    d23 = _d23({"never.mentioned": SHA_B})
    assert [f.kind for f in vp.check_d23_coverage(page, d23)] == ["unaccounted"]


# --------------------------------------------------------------------------- #
# D24
# --------------------------------------------------------------------------- #

def _d24(digests: dict[str, set[str]], assumptions=(), n=1) -> dict:
    return {
        "path": "p", "n_targets": n, "digests": digests,
        "assumptions": list(assumptions),
    }


def test_a_d24_digest_mismatch_is_reported():
    page = vp.parse_page(make_page())
    found = vp.check_d24_digests(
        page, _d24({"cso.saps2022.small_area": {SHA_B}}))
    assert [f.kind for f in found] == ["mismatch"]


def test_a_d24_source_the_page_does_not_cite_is_reported():
    page = vp.parse_page(make_page())
    found = vp.check_d24_digests(page, _d24({"cso.housing.trs05": {SHA_B}}))
    assert [f.kind for f in found] == ["not-cited"]


def test_a_compound_d24_target_is_not_called_a_mismatch():
    """One target, two cubes, one digest that is neither file's."""
    page = vp.parse_page(make_page())
    found = vp.check_d24_digests(page, _d24({"a.b.c + d.e.f": {SHA_B}}))
    assert [f.kind for f in found] == ["compound-target"]
    assert "a.b.c" in found[0].detail


def test_two_digests_for_one_source_in_d24_is_reported():
    page = vp.parse_page(make_page())
    found = vp.check_d24_digests(
        page, _d24({"cso.saps2022.small_area": {SHA_A, SHA_B}}))
    assert [f.kind for f in found] == ["inconsistent-in-d24"]


def test_d24_declaring_no_assumptions_is_a_disagreement():
    page = vp.parse_page(make_page())
    found = vp.check_d24_assumptions(
        page, _d24({}, assumptions=()), {"A-01", "A-10"})
    assert [f.kind for f in found] == ["d24-declares-none"]
    assert "cannot be satisfied from D24" in found[0].detail


def test_an_assumption_d24_declares_and_the_page_misses_is_reported():
    page = vp.parse_page(make_page(assumptions="A-01"))
    found = vp.check_d24_assumptions(
        page, _d24({}, assumptions=("A-01", "A-15")), {"A-01", "A-15"})
    assert [(f.kind, f.subject) for f in found] == [
        ("in-d24-not-in-page", "A-15")
    ]


def test_an_assumption_the_page_claims_and_d24_does_not_is_reported():
    page = vp.parse_page(make_page(assumptions="A-01, A-10"))
    found = vp.check_d24_assumptions(
        page, _d24({}, assumptions=("A-01",)), {"A-01", "A-10"})
    assert [(f.kind, f.subject) for f in found] == [
        ("in-page-not-in-d24", "A-10")
    ]


def test_a_flag_neither_registry_declares_is_reported():
    page = vp.parse_page(make_page(assumptions="A-01, A-999"))
    found = vp.check_d24_assumptions(
        page, _d24({}, assumptions=("A-01", "A-999")), {"A-01"})
    assert [(f.kind, f.subject) for f in found] == [
        ("undeclared-flag", "A-999")
    ]


def test_the_declared_flag_ids_cover_both_registries():
    ids = vp.declared_flag_ids()
    assert "A-01" in ids and "A-92" in ids


# --------------------------------------------------------------------------- #
# end to end
# --------------------------------------------------------------------------- #

def _fake_run_root(tmp_path: pathlib.Path, *, targets: list[dict]) -> pathlib.Path:
    root = tmp_path / "v1"
    (root / "evidence").mkdir(parents=True)
    (root / "evidence" / "d24_calibration_targets.json").write_text(
        json.dumps({"dataset": "D24", "targets": targets}), encoding="utf-8")
    return root


def test_a_missing_page_is_unrun_not_a_pass(tmp_path):
    code, report = vp.validate(tmp_path / "nope.md", tmp_path / "v1")
    assert code == 2
    assert report["unrun"]
    assert report["findings"] == []


def test_an_empty_page_is_unrun_not_a_pass(tmp_path):
    page = tmp_path / "PROVENANCE.md"
    page.write_text("# nothing here\n", encoding="utf-8")
    code, report = vp.validate(page, tmp_path / "v1")
    assert code == 2
    assert any("no dataset rows parsed" in u for u in report["unrun"])


def test_a_missing_d23_is_unrun_not_a_pass(tmp_path):
    page = tmp_path / "PROVENANCE.md"
    page.write_text(make_page(), encoding="utf-8")
    root = _fake_run_root(tmp_path, targets=[])
    code, report = vp.validate(page, root)
    assert code == 2
    assert any("D23_part" in u for u in report["unrun"])


def test_an_unsourced_citation_alone_makes_the_result_disagree(tmp_path):
    """No D23 on disk, so this one checks the UNSOURCED path's exit code."""
    page_text = make_page(
        sources_cell="`sources/derived/x.csv` — " + UNSOURCED,
        digest_rows=f"| `sources/derived/x.csv` | {UNSOURCED} — no manifest | — | — | — | — |",
    )
    parsed = vp.parse_page(page_text)
    found = vp.check_unsourced_declared(parsed)
    assert [f.kind for f in found] == ["unsourced"]


# --------------------------------------------------------------------------- #
# today's data
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not (PROJECT_ROOT / "docs" / "PROVENANCE.md").is_file(),
    reason="docs/PROVENANCE.md has not been generated",
)
def test_todays_page_parses_all_32_datasets():
    page = vp.parse_page(
        (PROJECT_ROOT / "docs" / "PROVENANCE.md").read_text(encoding="utf-8"))
    assert len(page.cited) == 32
    assert page.digests, "the digest register published nothing to compare"


@pytest.mark.skipif(
    not (PROJECT_ROOT / "docs" / "PROVENANCE.md").is_file(),
    reason="docs/PROVENANCE.md has not been generated",
)
def test_the_validator_runs_on_todays_data_and_does_not_error():
    """Exit 0 or 1 - a real verdict. Exit 2 means a check could not run."""
    code, report = vp.validate(
        PROJECT_ROOT / "docs" / "PROVENANCE.md", PROJECT_ROOT / "v1")
    assert code in (0, 1), f"a check could not be run: {report['unrun']}"
    assert report["checks"].get("D23"), "D23 was not read"
    assert report["checks"].get("D24"), "D24 was not read"
