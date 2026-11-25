"""I-067: a configuration must differ from the one it claims to be safer than.

This is the test that was missing, and its absence is the whole of I-067. Two
tests already covered D19 and both passed on a broken export:

* the schema audit checks that only D19's declared fields appear —
  ``import_wh`` **is** a declared field, so a configuration carrying it passes;
* the R09 test checks that no occupancy, presence or person-level field is
  transmitted — none was, so that passed too.

Neither asked the question that mattered: does ``compliance_only`` actually
carry less than ``home_30min``? It did not. It carried the complete
half-hourly import series, summing to exactly the same energy, and was
offered in design 7.8 as a **mitigation** for a configuration that fails the
inference test.

So these tests compare configurations against each other rather than each one
against the schema. The property is simple and was never asserted: a
configuration that is supposed to reveal less must contain less.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.edge.export import EXPORT_CONFIGS, build_export

#: One day at one minute, enough for every configuration to produce intervals.
MINUTES = 24 * 60


@pytest.fixture(scope="module")
def exports() -> dict[str, pd.DataFrame]:
    """One day of the same home, through every configuration."""
    idx = pd.date_range("2022-01-15", periods=MINUTES, freq="1min", tz="UTC")
    # A shape with a real evening peak and a real overnight floor, so a
    # configuration that carries the series carries something recognisable.
    t = np.arange(MINUTES) / 60.0
    imp = 200.0 + 900.0 * np.exp(-((t - 19.0) ** 2) / 4.0) \
        + 300.0 * np.exp(-((t - 8.0) ** 2) / 2.0)
    exp = np.zeros(MINUTES)
    out = {}
    for name, cfg in EXPORT_CONFIGS.items():
        out[name] = build_export(
            premises_id="MPRN-TEST", minute_index=idx, net_import_w=imp,
            net_export_w=exp, config=cfg, flex_event_id="FLEX-1",
            flex_compliance_pct=92.5, estate_id="EST-TEST",
        )
    return out


ENERGY_FIELDS = ("import_wh", "export_wh", "interval_peak_w", "interval_min_w")


def _carries_energy(df: pd.DataFrame) -> bool:
    """Does this export contain the interval energy series at all?"""
    for f in ENERGY_FIELDS:
        if f not in df.columns:
            continue
        v = pd.to_numeric(df[f], errors="coerce")
        if v.notna().any() and float(v.abs().sum()) > 0.0:
            return True
    return False


def test_compliance_only_carries_no_energy_series(exports):
    """I-067 itself.

    The configuration offered as the least-inference-risk mitigation must not
    contain the series an inference attack reads. Before the fix it contained
    the whole of it.
    """
    df = exports["compliance_only"]
    assert not _carries_energy(df), (
        "compliance_only carries the interval energy series. It is described "
        "as 'Only flexibility compliance leaves the home; least settlement "
        "value, least inference risk' and offered in design 7.8 as a "
        "mitigation - so a version of it that exports import_wh has the same "
        "inference risk as home_30min, which the 7.8 test measured at an "
        "occupancy AUC of 0.8655. This is I-067."
    )
    assert "flex_compliance_pct" in df.columns
    assert df["flex_compliance_pct"].notna().any(), (
        "compliance_only carries no compliance figure either, so it exports "
        "nothing at all - which is not a mitigation but a refusal"
    )


def test_a_configuration_that_reveals_less_contains_less(exports):
    """The property that was never asserted.

    For every pair where one configuration declares ``include_profile=False``
    and the other ``True``, the first must not carry the energy the second
    does. Written over the pairs rather than naming compliance_only, so a
    fifth configuration added later is covered without anyone remembering to
    extend this.
    """
    for a, cfg_a in EXPORT_CONFIGS.items():
        for b, cfg_b in EXPORT_CONFIGS.items():
            if cfg_a.include_profile or not cfg_b.include_profile:
                continue
            assert not _carries_energy(exports[a]), (
                f"{a} declares include_profile=False and still carries the "
                f"energy series that {b} carries. A configuration that is "
                f"supposed to reveal less must contain less."
            )


def test_no_two_configurations_are_the_same_data(exports):
    """Four configurations that differ only in their label are one configuration.

    Compared on the energy actually present, because that is what an attacker
    reads. Interval length legitimately differs, so the comparison is on the
    total and on whether the series is there at all - not on row counts.
    """
    signature: dict[str, tuple] = {}
    for name, df in exports.items():
        imp = pd.to_numeric(df.get("import_wh"), errors="coerce")
        total = (round(float(imp.fillna(0.0).sum()), 3)
                 if imp is not None else 0.0)
        signature[name] = (_carries_energy(df), total, len(df),
                           bool(df.get("building_energy_profile") is not None
                                and df["building_energy_profile"].notna().any()))
    # compliance_only must not share a signature with any profile-carrying one.
    for other, cfg in EXPORT_CONFIGS.items():
        if other == "compliance_only" or not cfg.include_profile:
            continue
        assert signature["compliance_only"] != signature[other], (
            f"compliance_only and {other} are the same data under different "
            f"names: {signature['compliance_only']}. That was I-067, measured "
            f"on the delivered package as an identical 163,137,265.9 Wh."
        )


def test_the_estate_aggregate_mixes_homes(exports):
    """Aggregation is a mitigation only if it actually aggregates."""
    df = exports["estate_aggregate"]
    cfg = EXPORT_CONFIGS["estate_aggregate"]
    assert cfg.aggregate_over == "estate"
    # One home's contribution must not be separable: the key must not be the
    # premises. Checked on the column rather than on the config flag, because
    # the flag is the claim and the column is the fact.
    if "premises_id" in df.columns:
        ids = set(df["premises_id"].dropna().astype(str))
        assert len(ids) <= 1, (
            f"the estate aggregate carries {len(ids)} distinct premises ids, "
            f"so individual homes are separable and the aggregation is not a "
            f"mitigation"
        )


def test_the_finer_interval_carries_more_rows_for_the_same_day(exports):
    """A sanity check on the interval length, which the AUCs are read against.

    home_15min must have twice home_30min's rows for one day. If it did not,
    the two privacy results would be the same measurement reported twice.
    """
    n15 = len(exports["home_15min"])
    n30 = len(exports["home_30min"])
    assert n15 == 2 * n30, (
        f"home_15min has {n15} rows and home_30min {n30} for the same day; "
        f"they should differ by exactly 2x, or the interval length is not "
        f"doing what the configuration says"
    )


def test_r09_still_holds_for_every_configuration(exports):
    """The fix must not have opened the door it was closing.

    No occupancy, presence or person-level field in any configuration. Stated
    as a property over the field names rather than against a fixed list, so a
    new leaky field name is caught.
    """
    forbidden = ("occup", "presence", "person", "household", "resident",
                 "n_people", "asleep", "awake")
    for name, df in exports.items():
        bad = [c for c in df.columns
               if any(f in c.lower() for f in forbidden)]
        assert not bad, f"{name} carries {bad}, which R09 forbids"


ENERGY_FIELDS_CONDITIONALLY_REQUIRED = (
    "import_wh", "export_wh", "interval_peak_w", "interval_min_w")


def test_the_energy_fields_are_present_for_every_profile_carrying_config(exports):
    """The conditional requirement the flat schema cannot state.

    I-076: D19 marked these four `required: true`, which made design 7.8's
    `compliance_only` mitigation **impossible to represent** - and that is why
    `include_profile` only ever gated the summary string. Gating the energy
    would have violated the contract, so the mitigation silently carried the
    full series and had home_30min's inference risk (I-067).

    The flag is now `false`, so the contract moves here, where a condition can
    live. Nothing is weakened: a profile-carrying export with a null energy
    field still fails, and only compliance_only may omit one.
    """
    for name, cfg in EXPORT_CONFIGS.items():
        df = exports[name]
        for field in ENERGY_FIELDS_CONDITIONALLY_REQUIRED:
            assert field in df.columns, f"{name} is missing {field} entirely"
            v = pd.to_numeric(df[field], errors="coerce")
            if cfg.include_profile:
                assert v.notna().all(), (
                    f"{name} carries a profile and has "
                    f"{int(v.isna().sum())} null {field} values. These are "
                    f"required for every configuration that carries a "
                    f"profile; D19's flag is false only so that "
                    f"compliance_only can omit them, and relaxing it must not "
                    f"relax anything else."
                )
            else:
                assert v.isna().all(), (
                    f"{name} declares include_profile=False and carries "
                    f"{int(v.notna().sum())} non-null {field} values. That is "
                    f"I-067: the mitigation carrying the series it is supposed "
                    f"to withhold."
                )


def test_the_schema_flag_and_the_conditional_rule_agree():
    """A guard against the flag being tightened again without the condition.

    If someone restores `required: true`, `compliance_only` becomes
    unrepresentable again and the next person to notice will do what the first
    one did: gate the summary and leave the series in. So the flag's state is
    pinned here, with the reason.
    """
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "baile_nua" / "schema"
         / "datasets.yaml").read_text(encoding="utf-8"))
    ds = spec["datasets"] if "datasets" in spec else spec
    fields = {f["name"]: f for f in ds["D19"]["fields"]}
    for field in ENERGY_FIELDS_CONDITIONALLY_REQUIRED:
        assert fields[field].get("required") is False, (
            f"D19.{field} is marked required again. That makes design 7.8's "
            f"compliance_only configuration impossible to represent, which is "
            f"I-076 - and the last time it was true, the mitigation carried "
            f"the full energy series instead (I-067). The requirement is "
            f"CONDITIONAL and lives in "
            f"test_the_energy_fields_are_present_for_every_profile_carrying_config."
        )
        assert "onditionally required" in str(fields[field].get("notes", "")), (
            f"D19.{field} is optional with no note saying the requirement is "
            f"conditional. An unexplained optional field reads as a field "
            f"nobody needs."
        )


def test_a_suppressed_energy_column_is_float_not_object(exports):
    """The dtype half of I-067's fix, and a latent schema break if wrong.

    `compliance_only` nulls four columns, and the writer concatenates its
    frame with the profile-carrying ones. Assigning `None` gives OBJECT
    dtype; today's pandas excludes an all-NA column when resolving the result
    and still produces float64, with a FutureWarning saying it will stop.
    When it stops, D19's import_wh is written as an object column and the
    Parquet schema changes under a library upgrade - I-066's lesson in a
    different place.
    """
    df = exports["compliance_only"]
    for field in ENERGY_FIELDS_CONDITIONALLY_REQUIRED:
        assert df[field].dtype == np.float64, (
            f"compliance_only's {field} is {df[field].dtype}, not float64. "
            f"An all-NA object column changes D19's Parquet schema the moment "
            f"pandas stops excluding it from dtype resolution."
        )
    # And the concatenation the writer performs must be warning-free.
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        joined = pd.concat(list(exports.values()), ignore_index=True)
        future = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert not future, (
        f"concatenating the four export configurations raises "
        f"{len(future)} FutureWarning(s): "
        f"{[str(w.message)[:110] for w in future]}"
    )
    assert joined["import_wh"].dtype == np.float64
