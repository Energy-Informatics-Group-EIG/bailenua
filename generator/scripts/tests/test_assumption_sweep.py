"""Tests for U30: the sweep of every remaining [A] flag against PxStat.

The sweep's whole value is that its negative results are trustworthy. A flag
that says "nothing public exists for this" is a decision to keep an assumption,
and if that claim were only prose it would rot silently the moment the CSO
published something. These tests are what make the claims checkable.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.sources import REGISTRY
from baile_nua.validation.assumption_sweep import (
    ASSUMPTION_FLAGS,
    BROAD_TERM_LIMIT,
    DELIBERATELY_BROAD,
    SWEEP_DATE,
    ZERO_HIT_CLAIMS,
    AssumptionFlag,
    load_catalogue,
    search,
    sweep,
    uncovered_files,
)


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


def test_the_catalogue_is_the_whole_catalogue(catalogue):
    """A sweep over a truncated catalogue would clear every flag falsely."""
    assert len(catalogue) > 10_000, (
        f"only {len(catalogue)} tables; the CSO publishes far more, and a "
        f"short catalogue makes every 'nothing published' verdict unearned"
    )
    assert all(e.matrix for e in catalogue)


def test_dimension_labels_are_searched_not_only_titles(catalogue):
    """The HAS02 lesson, as a test.

    HS023 is titled "Households". Everything that makes it answer A-04 and
    A-06 is in its dimensions. If the search ever regressed to titles only,
    this is the test that would catch it.
    """
    hits = search(r"appliance", catalogue)
    matrices = {h.matrix for h in hits}
    assert "HS023" in matrices
    hs023 = next(h for h in hits if h.matrix == "HS023")
    assert "appliance" not in hs023.title.lower(), (
        "HS023's title no longer makes this a dimension-only find; pick "
        "another table for the test rather than dropping it"
    )
    assert any("appliance" in d.lower() for d in hs023.dimensions)


def test_zero_hit_claims_really_return_zero(catalogue):
    """Every "nothing published" claim, against the catalogue as fetched.

    When one of these starts failing it is good news, not a broken test: it
    means an assumption can be retired. Follow the flag to its subject.
    """
    for flag_id, terms in sorted(ZERO_HIT_CLAIMS.items()):
        flag = next(f for f in ASSUMPTION_FLAGS if f.flag_id == flag_id)
        for term in terms:
            hits = search(term, catalogue)
            assert not hits, (
                f"{flag_id} ({flag.subject}) claims nothing is published, but "
                f"{term!r} now matches {len(hits)} tables, e.g. "
                f"{[(h.matrix, h.title) for h in hits[:3]]}. If one of them "
                f"measures the quantity, the assumption can be retired."
            )


def test_the_indoor_temperature_gap_is_the_decisive_one(catalogue):
    """I-032's claim, tested rather than asserted.

    PL-TEMP-01 reports PASS (declared band, unsourced) and that honesty rests
    on there being no Irish measurement to use instead. This is the test of
    that premise.
    """
    for term in (r"indoor temperat", r"dwelling temperat", r"room temperat"):
        assert not search(term, catalogue)


def test_no_search_term_is_too_broad_to_be_a_search(catalogue):
    """A term matching hundreds of tables has not searched; it has drowned.

    `BER\\b` matches 932 tables because "Number" and "Member" contain "ber".
    Terms that are broad on purpose are declared, so the breadth is a choice
    on the record rather than an accident.
    """
    for flag in ASSUMPTION_FLAGS:
        for term in flag.search_terms:
            n = len(search(term, catalogue))
            if term in DELIBERATELY_BROAD:
                continue
            assert n <= BROAD_TERM_LIMIT, (
                f"{flag.flag_id}: {term!r} matches {n} tables, so it did not "
                f"narrow anything. Anchor it, or declare it in "
                f"DELIBERATELY_BROAD with the reason."
            )


def test_the_broad_terms_really_are_broad(catalogue):
    """The exemption list must not accumulate terms that do not need it.

    It is currently empty, which is the measured result: every term in use
    matches at most 99 tables. If a term is ever added here, it has to earn
    the exemption.
    """
    for term in sorted(DELIBERATELY_BROAD):
        n = len(search(term, catalogue))
        assert n > BROAD_TERM_LIMIT, (
            f"{term!r} matches only {n} tables, inside the limit of "
            f"{BROAD_TERM_LIMIT}, so it does not need the exemption; remove "
            f"it so the exemption list stays meaningful"
        )


def test_the_limit_rejects_a_genuinely_unanchored_term(catalogue):
    """Exercise the guard itself, so an empty exemption list is not vacuous.

    This is the real case: `BER\\b` without a left boundary matches through
    "Number" and "Member" and finds hundreds of census tables about anything
    at all. Anchored, it matches a handful. The guard has to separate the two.
    """
    unanchored = len(search(r"BER\b", catalogue))
    anchored = len(search(r"\bBER\b", catalogue))
    assert unanchored > BROAD_TERM_LIMIT, (
        f"the motivating case no longer trips the limit ({unanchored} hits); "
        f"either the catalogue or the limit has changed and the guard needs "
        f"a new example"
    )
    assert anchored <= BROAD_TERM_LIMIT
    assert anchored < unanchored / 10


def test_every_a_flag_in_the_tree_is_accounted_for():
    """No assumption may sit outside the sweep.

    The negative-control discovery lesson: eight of seventeen controls were
    never in pytest because a test imported a hand-written list. The tree is
    the authority on where `[A]` appears, and anything the sweep has not
    claimed shows up here.
    """
    missing = uncovered_files()
    assert not missing, (
        f"these files carry an [A] flag that no sweep entry names: {missing}"
    )


def test_a_retired_or_found_verdict_must_name_a_declared_fetched_source():
    """An unused source retires nothing, and an unfetched one proves nothing."""
    for flag in ASSUMPTION_FLAGS:
        if flag.verdict not in ("RETIRED", "SOURCE_FOUND"):
            assert not flag.sources, (
                f"{flag.flag_id} is {flag.verdict} but names sources; either "
                f"the verdict or the sources is wrong"
            )
            continue
        assert flag.sources
        for key in flag.sources:
            assert key in REGISTRY, f"{flag.flag_id}: {key} is not declared"
            src = REGISTRY[key]
            assert src.manifest_path.exists(), (
                f"{flag.flag_id}: {key} has no manifest, so it was never "
                f"fetched and cannot support a {flag.verdict} verdict"
            )


def test_a_source_found_verdict_must_name_the_step_that_will_use_it():
    """HAS02 sat unused for four days. A found source needs an owner."""
    for flag in ASSUMPTION_FLAGS:
        if flag.verdict == "SOURCE_FOUND":
            assert flag.owning_step, flag.flag_id


def test_retires_if_is_written_for_every_flag():
    """The standard of evidence is declared, not set by what was found."""
    for flag in ASSUMPTION_FLAGS:
        assert len(flag.retires_if) > 20, flag.flag_id
        assert len(flag.verdict_note) > 80, flag.flag_id


def test_flag_ids_are_unique():
    ids = [f.flag_id for f in ASSUMPTION_FLAGS]
    assert len(ids) == len(set(ids))


def test_a_flag_cannot_be_built_without_search_terms():
    with pytest.raises(ValueError, match="needs search terms"):
        AssumptionFlag(
            flag_id="X-01", subject="s", where=("w",), assumed="a",
            retires_if="something published", search_terms=(),
            verdict="KEPT", verdict_note="x" * 90,
        )


def test_a_retired_verdict_cannot_be_declared_without_a_source():
    with pytest.raises(ValueError, match="must name the source"):
        AssumptionFlag(
            flag_id="X-02", subject="s", where=("w",), assumed="a",
            retires_if="something published", search_terms=(r"x",),
            verdict="RETIRED", verdict_note="x" * 90,
        )


def test_the_sweep_date_matches_the_catalogue_retrieval_date():
    """A verdict is only as current as the catalogue it was taken over."""
    import json

    manifest = json.loads(
        REGISTRY["cso.pxstat.collection"].manifest_path.read_text()
    )
    assert manifest["retrieved_at"] == SWEEP_DATE


def test_the_sweep_record_is_complete(catalogue):
    rec = sweep(catalogue)
    assert rec["n_flags"] == len(ASSUMPTION_FLAGS)
    assert rec["label"] == "UNVALIDATED SIMULATION EVIDENCE"
    assert sum(rec["verdict_counts"].values()) == len(ASSUMPTION_FLAGS)
    for f in rec["flags"]:
        assert f["searched"], f["flag_id"]
        for t in f["searched"]:
            assert "n_hits" in t and "term" in t
