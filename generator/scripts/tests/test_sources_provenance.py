"""Does each declared source actually contain what the registry says it does?

I-053: two vital-statistics sources were declared under crossed matrices -
`births_by_age_of_mother` pointed at VSA09, which publishes **deaths**, and
`deaths_by_age_sex` pointed at VSA17, which publishes **births**. Neither
carried an age dimension at all. The error survived for a week because nothing
had ever opened the files: sweep flag A-25 scheduled their first use for week 2
step 5, so the registry's claim went untested until then.

A declared source that nothing consumes is an unverified claim. The registry
records *intent*; only reading the file tests it. These tests read every
fetched JSON-stat source and compare what it says about itself - its own
`label` and its `extension.matrix` - against what the registry declared.

The overlap threshold is **measured, not declared**: across the 34 fetched
JSON-stat sources the lowest real overlap is 0.40 (CD488 and F2063, whose
declared titles add the dimension breakdowns that the CSO's short label
omits), while the two I-053 mismatches score 0.00. The threshold sits below
every real value and far above both failures.
"""

from __future__ import annotations

import json
import re
import unicodedata

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.sources import REGISTRY, require

#: Words that carry no subject matter and would inflate any overlap score.
_STOPWORDS = frozenset(
    "the a an of by and or in to for per at with on from is are census vital "
    "statistics number total all over aged years year".split()
)

#: Measured against the corpus: see the module docstring. Below the lowest
#: real overlap (0.40) and far above the I-053 mismatches (0.00).
MIN_LABEL_OVERLAP = 0.25


def _content_words(text: str) -> set[str]:
    flat = unicodedata.normalize("NFKD", str(text)).lower()
    return {
        w for w in re.split(r"[^a-z]+", flat)
        if w and w not in _STOPWORDS and len(w) > 2
    }


def _overlap(file_label: str, declared_title: str) -> float:
    lw = _content_words(file_label)
    return len(lw & _content_words(declared_title)) / len(lw) if lw else 1.0


def _jsonstat_sources() -> list[tuple[str, str, str, str]]:
    """``(key, declared_title, file_label, matrix)`` for every fetched cube."""
    out = []
    for key, src in sorted(REGISTRY.items()):
        try:
            path = require(key)
        except Exception:
            continue
        if path.suffix != ".json":
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = doc.get("label")
        matrix = (doc.get("extension") or {}).get("matrix")
        if not label or not matrix:
            continue
        out.append((key, src.title, str(label), str(matrix)))
    return out


def test_there_are_json_stat_sources_to_check():
    """A guard that silently checks nothing is worse than no guard."""
    rows = _jsonstat_sources()
    assert len(rows) >= 30, (
        f"only {len(rows)} JSON-stat sources were readable; either the "
        f"fetches are missing or the reader has stopped recognising them"
    )


@pytest.mark.parametrize("row", _jsonstat_sources(), ids=lambda r: r[0])
def test_the_declared_title_names_the_matrix_the_file_came_from(row):
    """A crossed matrix code is the cheapest version of I-053 to catch."""
    key, title, _label, matrix = row
    assert matrix.lower() in title.lower(), (
        f"{key}: the file is PxStat matrix {matrix}, which the declared title "
        f"does not name: {title!r}. Naming the matrix in the title is what "
        f"makes a crossed declaration visible without opening the file."
    )


@pytest.mark.parametrize("row", _jsonstat_sources(), ids=lambda r: r[0])
def test_the_declared_title_describes_what_the_file_says_it_is(row):
    """The I-053 guard proper: the subject matter has to agree."""
    key, title, label, matrix = row
    score = _overlap(label, title)
    assert score >= MIN_LABEL_OVERLAP, (
        f"{key} ({matrix}) declares the title {title!r} but the file calls "
        f"itself {label!r} - content-word overlap {score:.2f}, below the "
        f"measured floor of {MIN_LABEL_OVERLAP}. This is the I-053 failure: "
        f"the registry is describing a different table from the one fetched."
    )


def test_the_guard_catches_the_i_053_mismatch():
    """The guard has to fail on the real historical error, or it proves nothing."""
    # The two declarations as they actually stood, with the file labels the
    # fetched bytes actually carried.
    assert _overlap(
        "Deaths and Death Rates per 1,000 population",
        "Vital statistics: births by age of mother (VSA09)",
    ) < MIN_LABEL_OVERLAP
    assert _overlap(
        "Births",
        "Vital statistics: deaths by age and sex (VSA17)",
    ) < MIN_LABEL_OVERLAP


def test_every_source_declares_its_exposure_and_use():
    """D24: a source with no declared use cannot be audited for leakage."""
    for key, src in sorted(REGISTRY.items()):
        assert src.intended_use, key
        assert src.used_for, key
        assert src.licence, key
        assert src.publisher, key


# --------------------------------------------------------------------------- #
# the manifest is what the register publishes, so it must not drift
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "key", sorted(REGISTRY), ids=lambda k: k,
)
def test_the_manifest_matches_the_declaration(key):
    """`sources/SOURCES.md` is generated from the manifests, not the registry.

    So a declaration that changes without the manifest being rewritten leaves
    the published register asserting the old thing — and the field that
    matters most there is **exposure**, which is what a reader consults to
    know whether a source may validate what it calibrated (design 7.1).

    That is not hypothetical. `seai.ber.research_tool` was re-declared
    tuning-exposed for fabric once the model's U-values were derived from it,
    and the register went on reading `none` because `fetch()` short-circuits
    when the bytes already match. It now detects declaration drift and
    rewrites the manifest from the existing bytes.
    """
    import json

    src = REGISTRY[key]
    if not src.manifest_path.is_file():
        pytest.skip(f"{key} has not been fetched in this tree")
    man = json.loads(src.manifest_path.read_text(encoding="utf-8"))
    for field in ("intended_use", "model_development_exposure", "used_for",
                  "licence", "title", "publisher"):
        assert man.get(field) == getattr(src, field), (
            f"{key}: the manifest says {field}={man.get(field)!r} and the "
            f"declaration says {getattr(src, field)!r}. SOURCES.md is "
            f"generated from the manifest, so the published register is "
            f"wrong. Re-run `sources fetch` to refresh it."
        )


def test_a_tuning_exposed_source_says_so_in_its_used_for():
    """A reader skimming the register should not have to cross-reference.

    Exposure is a single word in a wide table. A source that calibrates
    something it could plausibly be used to validate should say which, in
    prose, where the use is described.
    """
    for key, src in sorted(REGISTRY.items()):
        if src.model_development_exposure != "tuning":
            continue
        assert src.used_for, key
        # Not a spelling check: the point is that the consequence is stated.
        lowered = src.used_for.lower()
        assert any(
            phrase in lowered
            for phrase in ("tuning-exposed", "not available to validate",
                           "cannot validate", "held out", "calibration axis",
                           "exposure")
        ), (
            f"{key} is tuning-exposed and its used_for does not say what that "
            f"rules out: {src.used_for!r}"
        )
