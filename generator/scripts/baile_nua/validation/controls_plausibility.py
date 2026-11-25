"""Expected-failure negative controls for the U27 plausibility suite.

U27 requires each plausibility check to carry "source, tolerance and an
expected-failure negative control". This is that set.

**Each control plants the fault the check was written for**, not an arbitrary
one. PL-TEMP-01 is broken with a 24.6 °C annual median, which is I-032's actual
measurement; PL-AREA-01 with an apartment larger than a terrace, which is
I-031's actual fault. A control that planted something else would prove the
check fires, without proving it fires on the thing that went wrong.

**Magnitudes are power-analysed** (U26, I-034). Every plausibility check is a
*deterministic* predicate — a measured ratio against a declared band, with no
sampling distribution — so the resolution is the band edge and the quantity to
report is the margin. Those margins are in
`baile_nua.validation.control_power_audit`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.plausibility.suite import CHECKS, run_suite
from baile_nua.validation.negative_control import NegativeControl, register

__all__ = ["PlausibilityCheckFired", "PLAUSIBILITY_CONTROL_MAGNITUDES"]

ROOT = Path(__file__).resolve().parents[3]
_E1_PACKAGE = ROOT / "v1"
_E1_DIAGNOSTICS = ROOT / "v1" / "run_diagnostics.json"


class PlausibilityCheckFired(AssertionError):
    """A plausibility check correctly rejected an implausible package."""


#: Planted magnitude against the band edge, per control. Deterministic checks,
#: so these are exact rather than estimated.
PLAUSIBILITY_CONTROL_MAGNITUDES: dict[str, dict[str, Any]] = {
    "NC-W2-06": {
        "check": "PL-APPLSIZE-01", "band_edge": 0.05, "planted": 0.25,
        "margin_ratio": 5.00,
        "quantity": "ownership slope per additional occupant, probability/person",
        "note": (
            "The band is +/-0.05 per person around the published slope and "
            "HS219's dishwasher slope is 0.0293, so a planted 0.25 sits 0.22 "
            "beyond the band edge - 5x the resolution. The magnitude is set "
            "from the band, not chosen: 0.25 per person is also the smallest "
            "round value that makes ownership certain by six occupants, which "
            "is the failure mode a slope assumption actually risks."
        ),
    },
    "NC-W2-07": {
        "check": "PL-ROOMS-01", "band_edge": 1.5414, "planted": 0.0,
        "margin_ratio": 1.5414,
        "quantity": "detached-minus-apartment mean rooms, rooms",
        "note": (
            "PL-ROOMS-01 requires at least half of the census gradient, and "
            "Cork County's detached-minus-apartment gap is 3.0828 rooms, so "
            "the band edge is 1.5414 rooms. The control plants INDEPENDENCE - "
            "room counts shuffled across dwelling types - which is I-031's "
            "actual regime and drives the gap to approximately zero, a margin "
            "of 1.5414 rooms below the edge. Reported as an absolute margin "
            "rather than a ratio because the planted value is zero and a "
            "ratio against zero is undefined; the audit's margin_ratio "
            "carries the rooms of headroom instead."
        ),
    },
    "NC-W2-08": {
        "check": "PL-PEAK-01", "band_edge": 0.4630, "planted": 0.6059,
        "margin_ratio": 1.309,
        "quantity": "aggregate after-diversity load factor",
        "note": (
            "A year in which every day is LP1's own average day. No seasonal "
            "and no day-to-day variation, so the only thing wrong with it is "
            "that the load is spread too evenly - which is what the upper "
            "bound exists to catch, and one of the tells 7.9 audits for. The "
            "magnitude needs no tuning: a mean-day-repeated year has a load "
            "factor of 0.6059 against a band edge of 0.4630 (LP1's 0.4129 "
            "plus the 0.05 allowance) by construction. It is surgical - the "
            "evening peak hour is 18:00 and the overnight taper 1.72, both "
            "LP1's own values - so it fires on the load-factor term alone and "
            "not by being implausible in every respect."
        ),
    },
    "NC-W2-01": {
        "check": "PL-ELEC-01", "band_edge": 1.00, "planted": 1.60,
        "margin_ratio": 1.60,
        "quantity": "fossil-heated electricity as a ratio of its DBEREL01 cell",
        "note": (
            "1.60 is chosen, not arbitrary: E1's first device layer measured "
            "16.35 kWh/home/day against a Co. Cork mean of 4,186 kWh/year "
            "for everything, which is a ratio of about 1.43 (I-027). The "
            "control plants slightly worse than the real defect so the check "
            "is shown to catch the fault that actually occurred."
        ),
    },
    "NC-W2-02": {
        "check": "PL-TEMP-01", "band_edge": 23.0, "planted": 24.6,
        "margin_ratio": 1.07,
        "quantity": "annual median living-zone temperature, degrees C",
        "note": (
            "24.6 C is I-032's measured value exactly. The margin is only "
            "1.07x the band edge, and deliberately: the band's upper edge is "
            "23 C and the real fault sat at 24.6, so a control planted far "
            "beyond it would not demonstrate that the band is placed "
            "correctly. This is the thinnest margin in the set and the audit "
            "flags it."
        ),
    },
    "NC-W2-03": {
        "check": "PL-AREA-01", "band_edge": "apartment < every house type",
        "planted": "apartment 120.8 m2, terraced 106.9 m2",
        "margin_ratio": 1.13,
        "quantity": "median floor area ordering by dwelling type",
        "note": (
            "I-031's actual measurement: the town's apartment median was "
            "120.8 m2 against a terraced median of 106.9. An ordering "
            "predicate has no numeric band, so the margin is the ratio by "
            "which the ordering was violated."
        ),
    },
    "NC-W2-04": {
        "check": "PL-APPL-01", "band_edge": "HAS02 share + 0.12",
        "planted": "dishwasher base prior 1.00",
        "margin_ratio": 2.2,
        "quantity": "appliance ownership base prior",
        "note": (
            "HAS02 2019 puts dishwasher ownership near 0.5, so a prior of "
            "1.00 - every household owns one - sits about 0.38 above the "
            "+0.12 ceiling. This is the control for the family that only "
            "became checkable when HAS02 was found."
        ),
    },
    "NC-W2-05": {
        "check": "PL-MIX-01", "band_edge": "3x the national ratio (3.92)",
        "planted": "10x the national ratio",
        "margin_ratio": 2.55,
        "quantity": "simulated electricity-to-gas ratio",
        "note": (
            "A town that burns almost no gas while using normal electricity. "
            "The band is already generous - 3x, because the simulated gas term "
            "is space heat alone - so the control has to clear that."
        ),
    },
}


def _load_e1() -> dict[str, Any]:
    if not _E1_DIAGNOSTICS.exists():
        raise RuntimeError(
            f"{_E1_DIAGNOSTICS} is absent; the plausibility controls perturb "
            f"the real E1 package rather than a hand-built one, so that a "
            f"control cannot pass against a fixture the real suite never sees"
        )
    return json.loads(_E1_DIAGNOSTICS.read_text(encoding="utf-8"))


def _run_single(check_id: str, diagnostics: dict[str, Any],
                d16: pd.DataFrame | None = None,
                d19: pd.DataFrame | None = None) -> dict[str, Any]:
    """Run one check against a perturbed package view."""
    import tempfile

    check = next(c for c in CHECKS if c.check_id == check_id)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ground_truth").mkdir(parents=True)
        (root / "observable").mkdir(parents=True)
        if d16 is not None:
            from baile_nua.io import write_dataset
            write_dataset(d16, "D16", root / "ground_truth" / "D16_part000.parquet")
        if d19 is not None:
            d19.to_parquet(root / "observable" / "D19_part000.parquet",
                           index=False)
        dpath = root / "run_diagnostics.json"
        dpath.write_text(json.dumps(diagnostics, default=str), encoding="utf-8")
        return run_suite(
            package_root=root, diagnostics_path=dpath, checks=(check,)
        )["results"][0]


def _expect_fired(result: dict[str, Any], check_id: str) -> None:
    if result["outcome"] == "FAIL":
        raise PlausibilityCheckFired(
            f"plausibility check {check_id} rejected the package: measured "
            f"{result['measured']} against {result['reference']} "
            f"(tolerance {result['tolerance']})"
        )
    raise AssertionError(
        f"{check_id} returned {result['outcome']} on a deliberately "
        f"implausible package; measured {result['measured']}"
    )


# --------------------------------------------------------------------------- #
# NC-W2-01  electricity far above its cell (the I-027 fault)
# --------------------------------------------------------------------------- #

def _build_elec() -> dict[str, Any]:
    d = _load_e1()
    for row in d["annual_electricity"]["per_dwelling"]:
        if not row["heats_with_electricity"] and row.get("d24_target_kwh_yr"):
            row["simulated_kwh_yr"] = round(1.60 * row["d24_target_kwh_yr"], 1)
    return d


register(NegativeControl(
    control_id="NC-W2-01",
    title="A package whose electricity is 1.6x its CSO cell (the I-027 fault)",
    design_ref="U27; 9.3 negative-control rule; I-027",
    intended_test="baile_nua.plausibility PL-ELEC-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-ELEC-01 rejected the package",
    build=_build_elec,
    invoke=lambda d: _expect_fired(_run_single("PL-ELEC-01", d), "PL-ELEC-01"),
    must_still_pass=(
        ("the real E1 package passes PL-ELEC-01",
         lambda _d: _assert_passes("PL-ELEC-01")),
    ),
))


# --------------------------------------------------------------------------- #
# NC-W2-02  a 24.6 C annual median (I-032's measured value)
# --------------------------------------------------------------------------- #

def _build_temp() -> pd.DataFrame:
    import numpy as np

    rng = np.random.default_rng(20261009)
    n = 20_000
    base = pd.Timestamp("2022-01-01", tz="UTC")
    # Shifted so the median lands at I-032's measured 24.6 C, with the same
    # kind of summer tail that produced it.
    temps = rng.normal(24.6, 4.0, n)
    temps[: n // 5] = rng.normal(34.0, 6.0, n // 5)
    return pd.DataFrame({
        "ts": base + pd.to_timedelta(np.arange(n) * 15, unit="m"),
        "building_id": [f"B-{i % 50:06d}" for i in range(n)],
        "temp_living_c": temps,
        "temp_sleep_c": temps - 2.0,
        "temp_env_c": temps - 5.0,
        "rh_living_pct": 55.0,
        "co2_living_ppm": 600.0,
        "co2_sleep_ppm": 600.0,
        "dhw_tank_c": float("nan"),
        "heat_delivered_w": 0.0,
        "internal_gain_w": 300.0,
        "solar_gain_w": 0.0,
        "ach_effective": 0.4,
        "occupants_living": 1,
        "occupants_sleep": 0,
    })


register(NegativeControl(
    control_id="NC-W2-02",
    title="A package with a 24.6 C annual median indoor temperature (I-032)",
    design_ref="U27; I-032; 7.2",
    intended_test="baile_nua.plausibility PL-TEMP-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-TEMP-01 rejected the package",
    build=_build_temp,
    invoke=lambda f: _expect_fired(
        _run_single("PL-TEMP-01", _load_e1(), d16=f), "PL-TEMP-01"
    ),
    must_still_pass=(
        ("the real E1 package passes PL-TEMP-01",
         lambda _f: _assert_passes("PL-TEMP-01")),
    ),
))


# --------------------------------------------------------------------------- #
# NC-W2-03  an apartment larger than a terrace (the I-031 fault)
# --------------------------------------------------------------------------- #

def _build_area() -> dict[str, Any]:
    d = _load_e1()
    for row in d["annual_electricity"]["per_dwelling"]:
        if row["dwelling_type"] == "apartment":
            row["floor_area_m2"] = 120.8
        elif row["dwelling_type"] == "terraced":
            row["floor_area_m2"] = 106.9
    # Ensure both types exist, since the estate may be short of one.
    types = {r["dwelling_type"] for r in d["annual_electricity"]["per_dwelling"]}
    if not {"apartment", "terraced"} <= types:
        template = dict(d["annual_electricity"]["per_dwelling"][0])
        for t, area in (("apartment", 120.8), ("terraced", 106.9)):
            if t not in types:
                row = dict(template)
                row.update({"dwelling_type": t, "floor_area_m2": area,
                            "building_id": f"B-NC-{t[:3].upper()}"})
                d["annual_electricity"]["per_dwelling"].append(row)
    return d


register(NegativeControl(
    control_id="NC-W2-03",
    title="A package whose apartments are larger than its terraces (I-031)",
    design_ref="U27; I-031",
    intended_test="baile_nua.plausibility PL-AREA-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-AREA-01 rejected the package",
    build=_build_area,
    invoke=lambda d: _expect_fired(_run_single("PL-AREA-01", d), "PL-AREA-01"),
    must_still_pass=(
        ("the real E1 package passes PL-AREA-01",
         lambda _d: _assert_passes("PL-AREA-01")),
    ),
))


# --------------------------------------------------------------------------- #
# NC-W2-04  an ownership prior of 1.0 against a HAS02 share near 0.5
# --------------------------------------------------------------------------- #

class _PriorsPatched:
    """Context that raises a base prior above its HAS02 ceiling."""

    def __init__(self, appliance: str, value: float) -> None:
        self.appliance, self.value = appliance, value
        self._old: float | None = None

    def __enter__(self) -> None:
        from baile_nua.devices.appliances import OWNERSHIP_PRIORS

        self._old = OWNERSHIP_PRIORS[self.appliance]["base"]
        OWNERSHIP_PRIORS[self.appliance]["base"] = self.value

    def __exit__(self, *exc: object) -> None:
        from baile_nua.devices.appliances import OWNERSHIP_PRIORS

        OWNERSHIP_PRIORS[self.appliance]["base"] = self._old


def _build_prior() -> tuple[str, float]:
    return ("dishwasher", 1.00)


def _invoke_prior(spec: tuple[str, float]) -> None:
    appliance, value = spec
    with _PriorsPatched(appliance, value):
        result = _run_single("PL-APPL-01", _load_e1())
    _expect_fired(result, "PL-APPL-01")


register(NegativeControl(
    control_id="NC-W2-04",
    title="An appliance ownership prior of 1.00 against a HAS02 share near 0.5",
    design_ref="U27; HAS02; the Day-5 [A] priors",
    intended_test="baile_nua.plausibility PL-APPL-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-APPL-01 rejected the package",
    build=_build_prior,
    invoke=_invoke_prior,
    must_still_pass=(
        ("the real priors pass PL-APPL-01",
         lambda _s: _assert_passes("PL-APPL-01")),
    ),
))


# --------------------------------------------------------------------------- #
# NC-W2-05  a town that barely burns gas
# --------------------------------------------------------------------------- #

def _build_mix() -> dict[str, Any]:
    d = _load_e1()
    summary = d["annual_electricity"]["summary"]
    summary["gas_heated_space_heat"]["mean_space_heat_kwh_yr"] = round(
        float(summary["fossil_heated"]["mean_simulated_kwh_yr"]) / 13.07, 1
    )
    return d


register(NegativeControl(
    control_id="NC-W2-05",
    title="A town whose electricity-to-gas ratio is ten times the national one",
    design_ref="U27; SEI01",
    intended_test="baile_nua.plausibility PL-MIX-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-MIX-01 rejected the package",
    build=_build_mix,
    invoke=lambda d: _expect_fired(_run_single("PL-MIX-01", d), "PL-MIX-01"),
    must_still_pass=(
        ("the real E1 package passes PL-MIX-01",
         lambda _d: _assert_passes("PL-MIX-01")),
    ),
))


def _assert_passes(check_id: str) -> None:
    """The false-positive control: the real package must pass.

    Run against the actual E1 package on disk, not a fixture. A plausibility
    control that only ever saw a hand-built package could pass while the real
    suite failed, which is the opposite of what these are for.
    """
    result = run_suite(
        package_root=_E1_PACKAGE, diagnostics_path=_E1_DIAGNOSTICS,
        checks=(next(c for c in CHECKS if c.check_id == check_id),),
    )["results"][0]
    if result["outcome"] != "PASS":
        raise AssertionError(
            f"{check_id} reports {result['outcome']} on the real E1 package: "
            f"measured {result['measured']} against {result['reference']}. "
            f"The control cannot be trusted while the check fires on a correct "
            f"package."
        )

# --------------------------------------------------------------------------- #
# NC-W2-06  an ownership slope that makes a dishwasher certain by six people
# --------------------------------------------------------------------------- #

class _SlopePatched:
    """Context that raises a `per_person` slope past its HS219 band."""

    def __init__(self, appliance: str, value: float) -> None:
        self.appliance, self.value = appliance, value
        self._old: float | None = None

    def __enter__(self) -> None:
        from baile_nua.devices.appliances import OWNERSHIP_PRIORS

        self._old = OWNERSHIP_PRIORS[self.appliance]["per_person"]
        OWNERSHIP_PRIORS[self.appliance]["per_person"] = self.value

    def __exit__(self, *exc: object) -> None:
        from baile_nua.devices.appliances import OWNERSHIP_PRIORS

        OWNERSHIP_PRIORS[self.appliance]["per_person"] = self._old


def _build_slope() -> tuple[str, float]:
    return ("dishwasher", 0.25)


def _invoke_slope(spec: tuple[str, float]) -> None:
    appliance, value = spec
    with _SlopePatched(appliance, value):
        result = _run_single("PL-APPLSIZE-01", _load_e1())
    _expect_fired(result, "PL-APPLSIZE-01")


register(NegativeControl(
    control_id="NC-W2-06",
    title="An ownership slope of 0.25 per person against an HS219 slope of 0.029",
    design_ref="U27; U30; HS219; the Day-5 [A] per_person slopes",
    intended_test="baile_nua.plausibility PL-APPLSIZE-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-APPLSIZE-01 rejected the package",
    build=_build_slope,
    invoke=_invoke_slope,
    must_still_pass=(
        ("the real slopes pass PL-APPLSIZE-01",
         lambda _s: _assert_passes("PL-APPLSIZE-01")),
    ),
))


# --------------------------------------------------------------------------- #
# NC-W2-07  rooms drawn independently of dwelling type: I-031's actual regime
# --------------------------------------------------------------------------- #

def _census_shaped_population() -> tuple[list[str], list[int]]:
    """A population with the census's own rooms-by-type structure.

    Built from F2063 rather than from the town, so the control tests the
    CHECK and not the generator, and so it runs without a synthesis. Scaled to
    roughly a thousand dwellings - the town's order - because a check that only
    works at county counts would not be the check that runs on Baile Nua.
    """
    from baile_nua.population.joint_f2063 import county_rooms_by_dwelling_type

    ref = county_rooms_by_dwelling_type()
    types: list[str] = []
    rooms: list[int] = []
    total = sum(
        v["n_dwellings"] for k, v in ref.items() if k != "_reference"
    )
    for dtype, block in sorted(ref.items()):
        if dtype == "_reference":
            continue
        n_type = max(round(1100 * block["n_dwellings"] / total), 1)
        for room_label, share in sorted(block["share_by_rooms"].items()):
            for _ in range(int(round(n_type * share))):
                types.append(dtype)
                rooms.append(int(room_label))
    return types, rooms


def _build_rooms() -> dict[str, Any]:
    types, rooms = _census_shaped_population()
    # The fault: the SAME room multiset, assigned without regard to dwelling
    # type. This is exactly what produced I-031 - a 285.7 m2 three-bedroom
    # apartment - and it leaves every marginal intact, which is why a marginal
    # check could never have caught it.
    shuffled = sorted(rooms, key=lambda r: (r * 7919) % 104729)
    return {"types": types, "correct": rooms, "independent": shuffled}


def _invoke_rooms(spec: dict[str, Any]) -> None:
    from baile_nua.population.joint_f2063 import (
        rooms_by_dwelling_type_acceptance,
    )

    planted = rooms_by_dwelling_type_acceptance(
        spec["types"], spec["independent"]
    )
    if planted["passed"]:
        raise AssertionError(
            "PL-ROOMS-01 accepted a population whose room counts are "
            "independent of dwelling type, which is I-031's regime"
        )
    raise PlausibilityCheckFired("PL-ROOMS-01 rejected the package")


register(NegativeControl(
    control_id="NC-W2-07",
    title="Room counts independent of dwelling type, with every marginal intact",
    design_ref="U27; U30; Census 2022 F2063; I-031",
    intended_test="baile_nua.population.joint_f2063 PL-ROOMS-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-ROOMS-01 rejected the package",
    build=_build_rooms,
    invoke=_invoke_rooms,
    must_still_pass=(
        ("a census-shaped population passes PL-ROOMS-01",
         lambda s: _assert_rooms_ok(s)),
    ),
))


def _assert_rooms_ok(spec: dict[str, Any]) -> None:
    """False-positive control: the correct assignment must pass."""
    from baile_nua.population.joint_f2063 import (
        rooms_by_dwelling_type_acceptance,
    )

    rec = rooms_by_dwelling_type_acceptance(spec["types"], spec["correct"])
    if not rec["passed"]:
        raise AssertionError(
            "PL-ROOMS-01 rejected a population built from the census's own "
            f"rooms-by-type structure: {rec['per_dwelling_type']}"
        )

# --------------------------------------------------------------------------- #
# NC-W2-08  a year with no seasonality: every day the average day
# --------------------------------------------------------------------------- #

def _build_flat_year() -> pd.DataFrame:
    """A D19 view whose every day is LP1's mean day.

    Built from the reference itself rather than from the E1 package, because
    the fault being planted is the ABSENCE of variation and the cleanest way
    to plant it is to supply a year with none. Five homes, because the check's
    lower bound only applies at a thousand and the upper bound is what this
    control is for.
    """
    from baile_nua.plausibility.slp import lp1_reference

    ref = lp1_reference()
    day = ref["mean_diurnal_over_day_mean"]
    # Minute-of-day 15..1440 in the source; 1440 is midnight ending the day.
    shape = [day[m] for m in sorted(day)]
    start = pd.Timestamp("2022-01-01 00:00:00+00:00")
    n_days = 365
    rows = []
    for home in range(5):
        pid = f"MPRN-NCW208-{home:02d}"
        for d in range(n_days):
            base = start + pd.Timedelta(days=d)
            for i, frac in enumerate(shape):
                t0 = base + pd.Timedelta(minutes=15 * i)
                rows.append({
                    "premises_id": pid,
                    "interval_start": t0,
                    "interval_end": t0 + pd.Timedelta(minutes=15),
                    # 100 Wh is an arbitrary scale; a load factor is a ratio.
                    "import_wh": 100.0 * frac,
                    "export_wh": 0.0,
                    "interval_peak_w": 400.0 * frac,
                    "interval_min_w": 400.0 * frac,
                    "building_energy_profile": "nc-w2-08",
                    "flex_event_id": None,
                    "flex_compliance_pct": None,
                    "export_config": "home_15min",
                    "quality": "ok",
                })
    return pd.DataFrame(rows)


def _invoke_flat_year(frame: pd.DataFrame) -> None:
    result = _run_single("PL-PEAK-01", _load_e1(), d19=frame)
    _expect_fired(result, "PL-PEAK-01")


register(NegativeControl(
    control_id="NC-W2-08",
    title="A year with no seasonality: load spread too evenly to be real",
    design_ref="U27; I-039; ESB Networks SLP LP1 2022; 7.9 tell audit",
    intended_test="baile_nua.plausibility PL-PEAK-01",
    expected_exception=PlausibilityCheckFired,
    expected_message="PL-PEAK-01 rejected the package",
    build=_build_flat_year,
    invoke=_invoke_flat_year,
    must_still_pass=(
        ("the real E1 package's load factor is below the upper bound",
         lambda _f: _assert_load_factor_upper_bound_holds()),
    ),
))


def _assert_load_factor_upper_bound_holds() -> None:
    """False-positive control, on the term this control tests.

    PL-PEAK-01 as a whole currently FAILS on the E1 package - the overnight
    taper, I-044 - so `_assert_passes` would be the wrong false-positive
    control here: it would fail for a reason this control has nothing to do
    with. The honest narrow form is to assert the term being tested, and to
    say so rather than quietly using a weaker check.
    """
    result = run_suite(
        package_root=_E1_PACKAGE, diagnostics_path=_E1_DIAGNOSTICS,
        checks=(next(c for c in CHECKS if c.check_id == "PL-PEAK-01"),),
    )["results"][0]
    detail = result.get("detail") or {}
    if not detail.get("load_factor_upper_ok"):
        raise AssertionError(
            f"the real E1 package now exceeds PL-PEAK-01's load-factor upper "
            f"bound: measured {result.get('measured')} against "
            f"{result.get('reference')}"
        )
