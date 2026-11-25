"""The dataset catalogue must agree with the files it describes.

``DATASETS.md`` is the one document in the project that a reader would use to
decide whether a dataset is worth opening, so a figure in it that disagrees
with the file is worse than no document. These tests do not check the prose.
They check the three things that could silently go wrong:

* a row count or a column list that disagrees with the Parquet footers or the
  per-part manifests the engine wrote;
* a page-break count that no longer gives one dataset per page, which is the
  whole reason the breaks are there;
* a number written into the generator by hand, which is how a catalogue starts
  describing a run that no longer exists.

They are skipped, not failed, when ``v1/`` holds no parts: a checkout without
a run is a legitimate state and the catalogue is empty rather than wrong.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.report import datasets_md as DM

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def catalogue():
    cat = DM.build_catalogue(project_root=ROOT)
    if not any(f.parts for f in cat["facts"].values()):
        pytest.skip("no Parquet parts under v1/; nothing to cross-check")
    return cat


def test_every_row_count_matches_the_manifests_the_engine_wrote(catalogue):
    """Two independent counts of the same rows must agree.

    The catalogue counts rows from the Parquet footers. The engine wrote a
    manifest per part at the time it streamed it, carrying its own count. If
    those disagree, one of the two is describing a file that has since been
    replaced — which is exactly what happened to E1's evidence (I-082), one
    layer down.
    """
    for ds, f in catalogue["facts"].items():
        if not f.parts or not f.manifests:
            continue
        declared = 0
        for m in f.manifests:
            declared += int(json.loads(m.read_text(encoding="utf-8"))["rows"])
        assert declared == f.rows, (
            f"{ds}: the manifests the engine wrote total {declared:,} rows "
            f"and the Parquet footers total {f.rows:,}. The catalogue would "
            f"publish the footer figure, so one of the two is stale."
        )


def test_the_column_list_matches_the_manifest(catalogue):
    """The manifest's column list is the logical one; ours flattens structs.

    So the comparison is on top-level names. It is worth making because the
    first version of the generator read the footer alone and reported D19's
    ``building_energy_profile`` as declared-but-absent while listing its three
    leaves as undeclared extras — wrong in both directions, and invisible
    without a check like this.
    """
    for ds, f in catalogue["facts"].items():
        if not f.parts or not f.manifest:
            continue
        expected = set(f.manifest["columns"])
        got = {c.name.split(".", 1)[0] for c in f.columns}
        assert got == expected, (
            f"{ds}: the manifest lists {sorted(expected)} and the catalogue "
            f"derived {sorted(got)}"
        )


def test_one_page_break_per_dataset_plus_the_cover_contents_and_appendices(
        catalogue):
    """The breaks are the document's pagination; the count is the contract."""
    text = DM.render(catalogue)
    n = text.count(DM.PAGE_BREAK)
    n_datasets = len(catalogue["declared"])
    # cover + contents + one per dataset + appendices A to D (E ends the file)
    expected = 2 + n_datasets + 4
    assert n == expected, (
        f"{n} page breaks for {n_datasets} datasets; expected {expected} "
        f"(cover, contents, one per dataset, and after appendices A to D)"
    )


def test_every_declared_dataset_has_a_page_and_an_anchor(catalogue):
    text = DM.render(catalogue)
    for ds in catalogue["declared"]:
        assert f'<a id="{ds.lower()}"></a>' in text, f"{ds} has no anchor"
        assert f"## {ds} · " in text, f"{ds} has no page heading"
        assert f"[{ds}](#{ds.lower()})" in text, f"{ds} is not in the contents"


def test_every_dataset_page_carries_prose(catalogue):
    """A page with no description is a page that should not have shipped."""
    missing = [ds for ds in catalogue["declared"]
               if not DM.PROSE.get(ds, {}).get("description")]
    assert not missing, f"no description written for {missing}"
    thin = [ds for ds in catalogue["declared"]
            if not 4 <= len(DM.PROSE.get(ds, {}).get("points", [])) <= 6]
    assert not thin, (
        f"these pages do not have between four and six key points: {thin}")


def test_the_prose_contains_no_figures(catalogue):
    """The rule the whole document rests on.

    Descriptions may draw on the design; they may not carry numbers, because
    a number in the prose is a number not traceable to a file. Dataset
    identifiers and the fidelity and tier names are not figures, so they are
    allowed by name.
    """
    allowed = re.compile(
        r"(D\d{2}|[A-Z]\d|\br\d\b|1\.1|§\d|6\.\d|7\.\d|5\.\d)")
    offenders: list[tuple[str, str]] = []
    for ds, body in DM.PROSE.items():
        chunks = [body["description"], *body.get("points", [])]
        for chunk in chunks:
            stripped = allowed.sub("", chunk)
            for m in re.finditer(r"\b\d[\d,.]*\b", stripped):
                offenders.append((ds, m.group(0)))
    assert not offenders, (
        f"figures found in the catalogue's prose, which must come from the "
        f"files instead: {offenders}"
    )


def test_the_document_on_disk_is_what_the_generator_produces(catalogue):
    """DATASETS.md must not have been hand-edited.

    A catalogue that is edited by hand stops being generated from the files,
    and the next person to regenerate it silently reverts someone's
    correction. Only the generated-at line and the HEAD hash may differ, both
    of which move on every run.
    """
    path = ROOT / "DATASETS.md"
    if not path.exists():
        pytest.skip("DATASETS.md has not been generated yet")

    def normalise(s: str) -> str:
        s = re.sub(r"\| Generated \| [^|]+\|", "| Generated | — |", s)
        s = re.sub(r"at \d{4}-\d{2}-\d{2}T[\d:]+ from git `[0-9a-f]+`",
                   "at — from git ``", s)
        s = re.sub(r"`[0-9a-f]{40}`", "`—`", s)
        s = re.sub(r"git `[0-9a-f]{12}`", "git `—`", s)
        return s

    on_disk = normalise(path.read_text(encoding="utf-8"))
    fresh = normalise(DM.render(catalogue))
    assert on_disk == fresh, (
        "DATASETS.md differs from what the generator produces now. Either it "
        "was edited by hand, or the data under v1/ changed and it needs "
        "regenerating: python -m baile_nua.report.datasets_md"
    )


def test_a_present_dataset_reports_a_sample_and_a_span(catalogue):
    for ds, f in catalogue["facts"].items():
        if not f.parts:
            continue
        assert f.sample, f"{ds} is present and the catalogue has no sample"
        assert f.rows > 0, f"{ds} is present with no rows"
        assert f.n_bytes > 0, f"{ds} is present with no bytes"


def test_status_counts_add_up(catalogue):
    c = catalogue["counts"]
    assert c["present"] + c["partial"] + c["missing"] == c["declared"]
    assert c["declared"] == len(catalogue["declared"])
