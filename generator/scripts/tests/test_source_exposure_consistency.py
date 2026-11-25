"""A source read by both a model module and a scoring module must say `tuning`.

Three sources in this project were declared at an exposure that understated
what they had been used for, and each was found by accident rather than by a
check:

* **DBEREL01 / DBERNG01** were declared `tuning` and said why, but the
  consequence — that PL-ELEC-01 and PL-GAS-01 are therefore consistency
  checks and not independent validations — was unstated (I-058).
* **The SEAI BER Research Tool** was declared `none` and then the fabric was
  derived from it (week 3 step 1).
* **HETUS `tus_00startime`** was declared `none` while U32's sleep timing was
  derived from it *and* the awake-share fit scored the model against the same
  curve (I-060).

The pattern is always the same: exposure is set when a source is *fetched* and
nobody revisits it when a later step *uses* it differently. `fetch()` now
rewrites the manifest on declaration drift, which fixes the publishing half.
This is the other half — a check that fires when a new consumer appears.

The rule it enforces is deliberately crude, because a crude rule that runs is
worth more than a precise one that does not: a source referenced from a module
that **sets** model parameters and also from a module that **scores** the model
cannot be at exposure `none`. It is either calibration or validation, and if it
is both then the scoring is a consistency check and the declaration has to say
so.
"""

from __future__ import annotations

import pathlib

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.sources import REGISTRY

#: Packages whose job is to BUILD the model: anything here reading a source is
#: using it as a calibration input.
MODEL_PACKAGES = ("physics", "activity", "behaviour", "population", "devices",
                  "lifecourse", "engine", "weather")

#: Packages whose job is to SCORE the model.
SCORING_PACKAGES = ("plausibility", "validation", "report", "calibration")

#: Modules exempt from the scoring side, with the reason. `assumption_sweep`
#: reads the PxStat catalogue to search it, which is neither calibration nor
#: scoring; `sources_registry` declares everything by construction.
SCORING_EXEMPT = {
    "validation/assumption_sweep.py",
    "sources_registry.py",
}


def _root() -> pathlib.Path:
    import baile_nua

    return pathlib.Path(baile_nua.__file__).resolve().parent


def _consumers() -> dict[str, dict[str, set[str]]]:
    """For each source key, which model and scoring modules name it."""
    root = _root()
    out: dict[str, dict[str, set[str]]] = {
        key: {"model": set(), "scoring": set()} for key in REGISTRY
    }
    for path in root.rglob("*.py"):
        rel = str(path.relative_to(root))
        if rel in SCORING_EXEMPT or rel.startswith("sources"):
            continue
        package = rel.split("/")[0]
        side = ("model" if package in MODEL_PACKAGES
                else "scoring" if package in SCORING_PACKAGES else None)
        if side is None:
            continue
        text = path.read_text(encoding="utf-8")
        for key in REGISTRY:
            if _reads(text, key):
                out[key][side].add(rel)
    return out


#: Ways a module actually LOADS a source, as opposed to mentioning its key.
#: The distinction matters: `physics/fabric_assessed.py` names the held-out gas
#: tables in a constant that documents what the independent validation axis is,
#: and a scan that counted mentions flagged the held-out table as if the model
#: were built from it — a false positive that would have forced a correct
#: declaration to be changed.
_LOAD_PATTERNS = (
    r"require\(\s*{k}\s*\)",
    r"REGISTRY\[\s*{k}\s*\]",
    r"_cube\(\s*{k}\s*\)",
    r"_read_jsonstat\(\s*{k}\s*\)",
    r"_table\(\s*{k}\s*\)",
    # How a plausibility check names the reference it scores against.
    r"source_key\s*=\s*{k}",
    # A single-line assignment of the bare key, which is how
    # calibration/targets.py and the activity modules hold it before passing
    # it to a loader. Deliberately single-line: a key appearing as an element
    # of a multi-line tuple is a MENTION, which is what
    # physics/fabric_assessed.py does when it documents the independent
    # validation axis, and counting that flagged the held-out gas table as if
    # the model were built from it.
    r"^\s*\w+\s*=\s*{k}\s*$",
)


def _reads(text: str, key: str) -> bool:
    import re

    quoted = r"[\"']" + re.escape(key) + r"[\"']"
    for pattern in _LOAD_PATTERNS:
        if re.search(pattern.format(k=quoted), text, re.M):
            return True
    return False


CONSUMERS = _consumers()


@pytest.mark.parametrize(
    "key", sorted(k for k in CONSUMERS
                  if CONSUMERS[k]["model"] and CONSUMERS[k]["scoring"]),
    ids=lambda k: k,
)
def test_a_source_used_to_build_and_to_score_is_declared_tuning(key):
    """The crude rule, and the one that would have caught all three."""
    src = REGISTRY[key]
    both = CONSUMERS[key]
    assert src.model_development_exposure != "none", (
        f"{key} is read by a model module ({sorted(both['model'])}) and by a "
        f"scoring module ({sorted(both['scoring'])}), and is declared "
        f"exposure 'none'. If the model is built from it, scoring against it "
        f"is a consistency check and the declaration must say so. Set "
        f"exposure to 'tuning' (or 'design') and state the consequence in "
        f"used_for."
    )


@pytest.mark.parametrize(
    "key", sorted(k for k in REGISTRY
                  if REGISTRY[k].model_development_exposure == "tuning"),
    ids=lambda k: k,
)
def test_a_tuning_exposed_source_states_what_it_rules_out(key):
    """Exposure is one word in a wide table; the consequence needs prose."""
    src = REGISTRY[key]
    lowered = src.used_for.lower()
    assert any(
        phrase in lowered for phrase in
        ("tuning-exposed", "consistency", "not available to validate",
         "cannot validate", "not an independent", "held out")
    ), (
        f"{key} is tuning-exposed and its used_for does not say what that "
        f"rules out: {src.used_for!r}"
    )


def test_the_scan_actually_finds_consumers():
    """A guard that silently matches nothing is worse than no guard."""
    with_model = [k for k in CONSUMERS if CONSUMERS[k]["model"]]
    with_scoring = [k for k in CONSUMERS if CONSUMERS[k]["scoring"]]
    assert len(with_model) >= 5, with_model
    assert len(with_scoring) >= 3, with_scoring
    both = [k for k in CONSUMERS
            if CONSUMERS[k]["model"] and CONSUMERS[k]["scoring"]]
    assert both, (
        "no source is read by both sides, which given this project's history "
        "almost certainly means the scan is broken rather than that the "
        "problem is gone"
    )


def test_lp1_is_never_tuned_against():
    """The one source that must stay independent, and why.

    LP1 is the only independent check on the overnight load shape. I-052's
    gap at 23:00 and 06:00 could be closed by adjusting appliance timings
    until the model matched it — and that would destroy the only evidence the
    shape has. So LP1 must be read by scoring modules and never by a model
    module.
    """
    key = "esbn.rmds.slp_indexes_2022"
    src = REGISTRY[key]
    assert src.model_development_exposure == "none", (
        f"{key} is declared {src.model_development_exposure!r}. If anything "
        f"has been tuned against LP1, PL-PEAK-01 is no longer independent and "
        f"the overnight shape has no external check at all."
    )
    model_side = CONSUMERS[key]["model"]
    assert not model_side, (
        f"LP1 is read by model modules {sorted(model_side)}. It is the "
        f"independent reference for the load shape; reading it while building "
        f"the model is how that independence is lost."
    )


def test_the_one_source_where_section_level_exposure_matters():
    """DEAP is read to BUILD the fabric and to SCORE hot water, disjointly.

    The guard above flags it, correctly, as read by both sides. Forcing it to
    `tuning` would be wrong in one direction and leaving it unexamined wrong
    in the other:

    * the fabric retrofit U-values **are** derived from Appendix S (Tables S3
      and S4), which is a tuning use;
    * PL-DHW-01 scores hot-water volume against **Section 4**, and that is a
      genuine validation — D-043 built the demand from draw events tied to
      simulated activities rather than from DEAP's floor-area route,
      *precisely so the model could disagree with it*.

    Two disjoint parts of a 213-page document. The `exposure` field is
    per-source and cannot express that, so it stays `design` and the suite
    reports a design-exposed pass in its own category — neither counted as
    independent nor as a calibration input. Recorded as I-061 rather than
    resolved, because resolving it means section-level provenance, which is a
    schema change.
    """
    src = REGISTRY["seai.deap.manual_4_2_7"]
    assert src.model_development_exposure == "design"
    assert "SECTION-LEVEL" in src.used_for
    assert "I-061" in src.used_for
    assert "Appendix S" in src.used_for and "Section 4" in src.used_for
    both = CONSUMERS["seai.deap.manual_4_2_7"]
    assert both["model"] and both["scoring"], (
        "if DEAP stopped being read by both sides, this test and I-061 should "
        "be revisited rather than left asserting a situation that has gone"
    )
