"""The tell audit and the three delivery packages, tested on planted tells.

A tell audit that finds nothing is indistinguishable from one that looks at
nothing, so every check here is exercised against a frame built to trip it and
against one built not to. The same for the package separation rules: each must
refuse a package that breaks it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.release import packages as PK
from baile_nua.release import tell_audit as TA


# --------------------------------------------------------------------------- #
# the tell audit, on planted tells
# --------------------------------------------------------------------------- #

def test_a_sequential_id_is_caught_and_an_opaque_one_is_not():
    """Design 6.3: "IDs are opaque random strings, not sequential P-000001"."""
    seq = pd.DataFrame({"premises_id": [f"P-{i:06d}" for i in range(500)]})
    r = TA.audit_frame(dataset="D19", frame=seq, id_columns=("premises_id",))
    assert r["n_findings"] == 1
    assert r["findings"][0]["tell_class"] == "sequential_ids"
    assert r["findings"][0]["severity"] == "high"

    rng = np.random.default_rng(3)
    opaque = pd.DataFrame({"premises_id": [
        "MPRN-" + "".join(rng.choice(list("0123456789ABCDEF"), 20))
        for _ in range(500)]})
    r2 = TA.audit_frame(dataset="D19", frame=opaque,
                        id_columns=("premises_id",))
    assert r2["n_findings"] == 0, (
        f"an opaque hex id was reported as sequential: {r2['findings']}")


def test_a_counter_with_gaps_is_not_called_sequential():
    """The density half of the check.

    A sample of ids drawn from a wide range matches a counter's FORM and is not
    a counter. Without the density test, any id ending in digits would be
    flagged and the audit would be noise.
    """
    rng = np.random.default_rng(5)
    sparse = sorted(rng.choice(10_000_000, size=300, replace=False))
    df = pd.DataFrame({"premises_id": [f"MPRN-{i:08d}" for i in sparse]})
    r = TA.audit_frame(dataset="D19", frame=df, id_columns=("premises_id",))
    assert r["n_findings"] == 0, (
        "ids drawn sparsely from a wide range were called a counter; the "
        "density test is not doing its work")


def test_a_perfectly_regular_timestamp_is_caught():
    ts = pd.date_range("2022-01-01", periods=2000, freq="15min", tz="UTC")
    df = pd.DataFrame({"interval_start": ts})
    r = TA.audit_frame(dataset="D19", frame=df,
                       timestamp_columns=("interval_start",))
    assert any(f["tell_class"] == "timestamp_regularity"
               for f in r["findings"]), (
        "a stamp exactly on the quarter-hour for 2,000 intervals with one "
        "second-of-minute value was not flagged")
    # And a jittered one must not be.
    rng = np.random.default_rng(9)
    jit = ts + pd.to_timedelta(rng.integers(-20, 21, len(ts)), unit="s")
    r2 = TA.audit_frame(dataset="D19", frame=pd.DataFrame(
        {"interval_start": jit.sort_values()}),
        timestamp_columns=("interval_start",))
    assert not any(f["tell_class"] == "timestamp_regularity"
                   for f in r2["findings"])


def test_the_final_digit_check_does_not_fire_on_an_honest_resolution():
    """The bug this check had, turned into a test.

    Its first version tested the digit of ``value * 10000`` whatever the
    column's resolution was, so an integer-valued column failed by
    construction and D18 was reported with a chi-square of 2.5 million. A
    meter reporting whole watts is a real meter.
    """
    rng = np.random.default_rng(13)
    whole = pd.DataFrame({"value": rng.integers(1, 4000, 5000).astype(float)})
    r = TA.audit_frame(dataset="D18", frame=whole, value_columns=("value",))
    assert not any(f["tell_class"] == "final_digit_distribution"
                   for f in r["findings"]), (
        f"an integer-valued column with a uniform last digit was reported as "
        f"a quantisation signature: {r['findings']}")

    # But a column quantised to a coarse grid must fire.
    grid = pd.DataFrame({"value": (rng.integers(1, 400, 5000) * 10).astype(float)})
    r2 = TA.audit_frame(dataset="D18", frame=grid, value_columns=("value",))
    assert any(f["tell_class"] in ("final_digit_distribution",
                                   "suspiciously_round_values")
               for f in r2["findings"]), (
        "a column quantised to multiples of ten was not flagged")


def test_a_quality_column_with_only_ok_is_caught():
    """The highest-value check: a series that never went wrong."""
    clean = pd.DataFrame({"quality": ["ok"] * 1000})
    r = TA.audit_frame(dataset="D19", frame=clean)
    f = [x for x in r["findings"] if x["tell_class"] == "missing_failure_modes"]
    assert f and f[0]["severity"] == "high"

    real = pd.DataFrame({"quality": ["ok"] * 940 + ["estimated"] * 40
                         + ["missing"] * 12 + ["suspect"] * 5 + ["drift"] * 3})
    r2 = TA.audit_frame(dataset="D19", frame=real)
    assert not any(x["tell_class"] == "missing_failure_modes"
                   for x in r2["findings"])


def test_a_uniform_resolution_across_channels_is_caught():
    """The per-channel partition, which is the real D18 finding."""
    rng = np.random.default_rng(17)
    rows = []
    for ch in ("import_w", "export_w", "ct_circuit"):
        rows += [{"channel": ch, "value": float(v)}
                 for v in rng.integers(0, 3000, 400)]
    rows += [{"channel": "temp", "value": float(round(v, 2))}
             for v in rng.uniform(5, 25, 400)]
    r = TA.audit_frame(dataset="D18", frame=pd.DataFrame(rows))
    f = [x for x in r["findings"]
         if x["tell_class"] == "suspiciously_round_values"]
    assert f, "three exactly-integer channels beside a fractional one was not flagged"
    assert set(f[0]["detail"]["channels_exactly_integer"]) == {
        "import_w", "export_w", "ct_circuit"}


def test_the_manifest_check_catches_a_disclosed_provenance(tmp_path):
    """I-074, as a test."""
    good = tmp_path / "D18_part000.manifest.json"
    good.write_text(json.dumps({"dataset_id": "D18", "access_class": "OBS",
                                "quality": "ok"}), encoding="utf-8")
    r = TA.audit_manifests(manifest_paths=[good])
    assert r["n_disclosing"] == 0

    bad = tmp_path / "D19_part000.manifest.json"
    bad.write_text(json.dumps({
        "dataset_id": "D19",
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
    }), encoding="utf-8")
    r2 = TA.audit_manifests(manifest_paths=[bad])
    assert r2["n_disclosing"] == 1
    f = r2["findings"][0]
    assert f["severity"] == "critical"
    assert "UNVALIDATED" in f["detail"]["markers_found"]
    assert "organiser holds" in f["design_ref"]


def test_the_audit_says_what_it_did_not_check():
    """"The audit found nothing" must never read as "there are no tells"."""
    unchecked = TA.unchecked_tell_classes()
    assert "the tells nobody thought of" in unchecked
    r = TA.audit_observable_view(frames={"D19": pd.DataFrame(
        {"premises_id": ["MPRN-AAA1"] * 20, "quality": ["ok"] * 20})})
    assert set(r["unaudited_observable_datasets"]) >= {"D18", "D28", "D29",
                                                        "D30", "D31"}
    assert "did not look" in r["unaudited_is_not_clean"]
    assert "adversarial analyst" in r["this_is_not_the_adversarial_analyst"]


# --------------------------------------------------------------------------- #
# the three packages
# --------------------------------------------------------------------------- #

def test_a_package_that_discloses_provenance_is_refused_by_default(tmp_path):
    obs = tmp_path / "observable"
    obs.mkdir(parents=True)
    (obs / "D18_part000.parquet").write_bytes(b"")
    (obs / "D18_part000.manifest.json").write_text(
        json.dumps({"dataset_id": "D18",
                    "label": "UNVALIDATED SIMULATION EVIDENCE"}),
        encoding="utf-8")
    (tmp_path / "ground_truth").mkdir()
    with pytest.raises(PK.PackageError, match="disclose synthetic provenance"):
        PK.build_packages(root=tmp_path)
    # And it can be built deliberately, recording that it is not blind-safe.
    r = PK.build_packages(root=tmp_path, allow_provenance_disclosure=True)
    assert r["observable"]["blind_safe"] is False
    assert r["separation"]["all_rules_pass"] is False


def test_a_ground_truth_dataset_in_the_observable_view_is_caught(tmp_path):
    """The coarse prior check the field-level leakage test does not make."""
    obs = tmp_path / "observable"
    obs.mkdir(parents=True)
    # D11 is presence - ground truth - filed in the wrong directory.
    for name in ("D18_part000", "D11_part000"):
        (obs / f"{name}.parquet").write_bytes(b"")
        (obs / f"{name}.manifest.json").write_text(
            json.dumps({"dataset_id": name.split("_")[0]}), encoding="utf-8")
    (tmp_path / "ground_truth").mkdir()
    r = PK.build_packages(root=tmp_path)
    assert r["separation"]["gt_datasets_in_the_observable_view"] == ["D11"]
    assert r["separation"]["rule_1_no_gt_in_obs"] is False
    assert r["separation"]["all_rules_pass"] is False


def test_a_clean_package_passes_every_separation_rule(tmp_path):
    """The rules must be satisfiable, or they are not rules."""
    obs = tmp_path / "observable"
    obs.mkdir(parents=True)
    (obs / "D18_part000.parquet").write_bytes(b"")
    (obs / "D18_part000.manifest.json").write_text(
        json.dumps({"dataset_id": "D18", "access_class": "OBS",
                    "quality_vocabulary": ["ok", "estimated", "missing"]}),
        encoding="utf-8")
    gt = tmp_path / "ground_truth"
    gt.mkdir()
    (gt / "D11_part000.parquet").write_bytes(b"")
    r = PK.build_packages(root=tmp_path)
    assert r["separation"]["all_rules_pass"] is True
    assert r["observable"]["blind_safe"] is True


def test_the_evidence_view_reads_its_limitations_from_the_issue_log():
    """A limitations list kept separately from the issue log gets shorter."""
    lim = PK._limitations()
    assert len(lim) > 50, len(lim)
    ids = [x["issue"] for x in lim]
    # One entry per id, after the log's own convention is resolved: an issue
    # later closed or extended gets a SECOND heading with the same id, and
    # five ids have two. A list that shipped both would give a reader two
    # contradictory statuses for the same issue.
    assert len(ids) == len(set(ids)), (
        f"duplicate issue ids in the limitations: "
        f"{sorted({i for i in ids if ids.count(i) > 1})}")
    multi = [x for x in lim if x["n_entries_in_the_log"] > 1]
    assert multi, (
        "no issue has more than one log entry, so the duplicate-resolution "
        "path is untested - and five ids do have two headings")
    for x in multi:
        assert x["superseded_title"], x["issue"]
    # Closed issues must be distinguishable from open ones, or the
    # limitations list overstates what is still wrong.
    assert any(x["closed"] for x in lim)
    assert any(not x["closed"] for x in lim)
    # The issues this week's work raised must be in it, which is the property
    # that matters: a list that cannot see today's findings is decoration.
    for recent in ("I-069", "I-072", "I-073", "I-074"):
        assert recent in ids, f"{recent} is not in the limitations list"
    assert all(x["title"] for x in lim)


def test_the_three_packages_declare_who_receives_them():
    """6.3's own table. A package without an audience is not a package."""
    for name, spec in PK.PACKAGES.items():
        assert spec["receives"], name
        assert spec["contents"], name
    assert "blind evaluators" in PK.PACKAGES["observable"]["receives"]
    assert "never a model under test" in PK.PACKAGES["ground_truth"]["receives"]
    assert "everyone" in PK.PACKAGES["evidence"]["receives"]
    # D03 and D17 are GT datasets with an observable VIEW, and the distinction
    # has to be recorded or someone ships the dataset.
    assert set(PK.OBSERVABLE_VIEWS_OF_GT) == {"D03", "D17"}
    assert "redacted" in PK.OBSERVABLE_VIEWS_OF_GT["D03"]
    assert "aggregate" in PK.OBSERVABLE_VIEWS_OF_GT["D17"]
