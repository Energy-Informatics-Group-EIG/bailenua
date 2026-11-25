"""Tests for the device layer and its D24 targets.

The device layer had no public target at all until I-027, so none of these
tests could have existed. Their point is that the layer is now scoreable: a
rate can still be a declared assumption, but its CONSEQUENCE is measured
against a CSO figure read from a file.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.calibration import (
    TargetError,
    build_d24,
    electricity_per_dwelling_targets,
    meter_distribution_target,
    per_meter_target,
)
from baile_nua.calibration.targets import electricity_by_construction_targets
from baile_nua.devices.appliances import (
    PER_PERSON_APPLIANCES,
    SHARED_WITHIN_EPISODE,
    TRIGGERS,
    build_episodes,
)
from baile_nua.devices.signatures import (
    assert_library_consistent,
    shape_mean,
    signature_for,
)
from baile_nua.sources import REGISTRY


# --------------------------------------------------------------------------- #
# D24
# --------------------------------------------------------------------------- #

def test_every_d24_target_traces_to_a_registered_file_and_hash():
    """A target with no traceable source is the failure mode D24 exists to stop."""
    d = build_d24(2022)
    assert d["n_targets"] >= 50
    for row in d["targets"]:
        for key in str(row["source_key"]).split(" + "):
            assert key.strip() in REGISTRY, f"{row['target_id']} cites unregistered {key}"
        for sha in str(row["source_sha256"]).split(" + "):
            assert len(sha.strip()) == 64, f"{row['target_id']} has no full SHA-256"
        # 2022 is t0, so a target from another year must say why in its own
        # scope note rather than being silently compared to a 2022 simulation.
        if row["year"] != 2022:
            assert str(row["year"]) in str(row["scope_note"]) or (
                "latest year" in str(row["scope_note"]).lower()
            ), (
                f"{row['target_id']} is from {row['year']} but E1 simulates "
                f"2022, and its scope note does not say so: "
                f"{row['scope_note']}"
            )
            assert 2015 <= int(row["year"]) <= 2022, (
                f"{row['target_id']} is from {row['year']}, too far from t0"
            )
        assert len(str(row["scope_note"])) > 60, (
            f"{row['target_id']} has no scope note worth reading. A target "
            f"without its limits invites a comparison it cannot support."
        )


def test_the_held_out_table_is_declared_unexposed():
    """DBEREL02 must stay held out, and the reader must enforce it."""
    key = "cso.electricity.dbere102_by_dwelling_construction"
    assert REGISTRY[key].model_development_exposure == "none"
    rows = electricity_by_construction_targets(2022)
    assert rows and all(r.exposure == "none" for r in rows)


def test_the_tuned_table_is_declared_exposed():
    """DBEREL01 WAS used for tuning, and 7.1 requires that to be visible."""
    key = "cso.electricity.dbere101_by_dwelling_ber"
    assert REGISTRY[key].model_development_exposure == "tuning", (
        "the cooking trigger rates were tuned against DBEREL01. Declaring its "
        "exposure as anything else would make the E1 report overstate what the "
        "comparison establishes."
    )


def test_per_meter_target_is_a_plausible_irish_figure():
    """Guards the two-table division, which is easy to get upside down."""
    t = per_meter_target(2022)
    assert 2500.0 <= float(t.value) <= 6500.0, (
        f"Co. Cork residential consumption came out at {t.value} kWh per meter "
        f"per year. An Irish dwelling uses roughly 3,000 to 5,000, so the "
        f"numerator and denominator are probably the wrong way round or the "
        f"GWh were not converted."
    )


def test_meter_distribution_bands_are_internally_consistent():
    t = meter_distribution_target(2022)
    bands = t.value["bands"]
    assert abs(sum(bands.values()) - t.value["total"]) <= 1.0
    assert t.value["total"] > 2_000_000


# --------------------------------------------------------------------------- #
# the sharing declaration (I-027)
# --------------------------------------------------------------------------- #

def test_every_triggered_appliance_declares_whether_it_is_shared():
    """The declaration gap that multiplied a household's load by its size.

    Triggers fire per activity interval and the activity engine emits one per
    PERSON, so an undeclared appliance is triggered once per person. For a
    2.94-person estate that is a 3x error in its daily energy, and nothing else
    in the system would notice.
    """
    triggered = {
        rule["appliance"] for rules in TRIGGERS.values() for rule in rules
    }
    undeclared = triggered - SHARED_WITHIN_EPISODE - PER_PERSON_APPLIANCES
    assert not undeclared, (
        f"these appliances are triggered but declare no sharing behaviour: "
        f"{sorted(undeclared)}"
    )
    both = SHARED_WITHIN_EPISODE & PER_PERSON_APPLIANCES
    assert not both, f"declared both shared and per-person: {sorted(both)}"


class _Iv:
    def __init__(self, pid, a, b, activity, zone="kitchen", loc="building"):
        self.person_id, self.start_min, self.end_min = pid, a, b
        self.activity, self.zone, self.location_kind = activity, zone, loc
        self.activity_id = None

    @property
    def duration_min(self):
        return self.end_min - self.start_min


def test_overlapping_intervals_become_one_episode_with_the_right_count():
    eps = build_episodes([
        _Iv("P-1", 800, 830, "eating_main"),
        _Iv("P-2", 810, 840, "eating_main"),
        _Iv("P-3", 815, 835, "eating_main"),
    ])
    assert len(eps) == 1
    assert eps[0].n_participants == 3
    assert (eps[0].start_min, eps[0].end_min) == (800, 840)


def test_back_to_back_intervals_stay_two_episodes():
    """One person cooking after another really is two cooking events."""
    eps = build_episodes([
        _Iv("P-1", 800, 820, "cooking"),
        _Iv("P-2", 820, 840, "cooking"),
    ])
    assert len(eps) == 2


def test_the_same_activity_in_two_zones_stays_two_episodes():
    """Two people watching television in different rooms use two sets."""
    eps = build_episodes([
        _Iv("P-1", 1200, 1260, "tv_screens", zone="living"),
        _Iv("P-2", 1200, 1260, "tv_screens", zone="bedroom"),
    ])
    assert len(eps) == 2
    assert all(e.n_participants == 1 for e in eps)


def test_out_of_home_intervals_start_no_appliance():
    assert build_episodes([_Iv("P-1", 600, 700, "cooking", loc="venue")]) == []


def test_episode_order_is_deterministic():
    ivs = [
        _Iv("P-2", 810, 840, "eating_main"),
        _Iv("P-1", 300, 330, "cooking"),
        _Iv("P-3", 1200, 1260, "tv_screens", zone="living"),
    ]
    a = [(e.activity, e.zone, e.start_min) for e in build_episodes(ivs)]
    b = [(e.activity, e.zone, e.start_min) for e in build_episodes(list(reversed(ivs)))]
    assert a == b, "episode order must not depend on input order: cycle ids depend on it"


# --------------------------------------------------------------------------- #
# the signature library
# --------------------------------------------------------------------------- #

def test_signature_library_is_self_consistent():
    assert assert_library_consistent()


def test_the_oven_thermostat_switches_rather_than_ramps():
    """A linearly interpolated thermostat averaged 0.63 of rating (I-027).

    The shape's mean is the whole quantity of interest: at 0.63 a one-hour bake
    is 1.51 kWh, which no domestic oven does.
    """
    sig = signature_for("oven")
    mean = shape_mean(sig)
    assert 0.40 <= mean <= 0.55, (
        f"the oven's shape averages {mean:.3f} of its {sig.peak_w:.0f} W "
        f"rating, implying {sig.peak_w * mean * sig.nominal_duration_s / 3600 / 1000:.2f} "
        f"kWh for a bake. A real 180 C bake is 1.0 to 1.2 kWh: about 25% duty "
        f"after preheat."
    )
    # Transitions must be narrow, or interpolation reintroduces the ramp.
    xs = [a for a, _ in sig.shape]
    ys = [b for _, b in sig.shape]
    widths = [
        xs[i + 1] - xs[i]
        for i in range(len(xs) - 1)
        if abs(ys[i + 1] - ys[i]) > 0.5
    ]
    assert widths and max(widths) <= 0.03, (
        f"a thermostat switches; the widest on/off transition in the oven's "
        f"shape spans {max(widths) if widths else 0:.2f} of the cycle"
    )


def test_the_gas_targets_exist_and_are_split_tuned_against_held_out():
    """49 of the 50 estate homes heat with gas (I-031).

    Without a gas target the electricity comparison cannot see their heating at
    all, which is how a 285 m2 apartment survived five days: only the single
    electrically heated home exposed it.
    """
    from baile_nua.calibration.targets import (
        gas_by_construction_targets,
        gas_per_dwelling_targets,
    )

    tuned = gas_per_dwelling_targets(2022)
    held = gas_by_construction_targets(2022)
    assert tuned and held
    assert all(t.exposure == "tuning" for t in tuned)
    assert all(t.exposure == "none" for t in held), (
        "DBERNG02 is the held-out gas table and must stay unexposed"
    )
    assert REGISTRY["cso.gas.dberng02_by_dwelling_construction"].\
        model_development_exposure == "none"


def test_gas_use_is_flat_across_ber_bands_and_rises_with_dwelling_type():
    """What DBERNG01 actually says, pinned so nobody "fixes" the model to it.

    I wrote this test first asserting that gas use falls as the rating
    improves, which is what insulation physics alone predicts. The data refuses
    it: A-B rated detached houses use MORE gas (14,618 kWh) than F-G ones
    (13,292). Across every dwelling type the spread between the best and worst
    band is only 4 to 7%, while the spread ACROSS dwelling types is 84%
    (apartment 7,458 to detached 13,730).

    That is comfort-taking. A better-insulated home is heated warmer, for
    longer, in more rooms; a poorly-insulated one is heated less because it
    costs more. Measured consumption therefore tracks dwelling SIZE, not
    fabric quality.

    It matters for E1 because the F1 physics heats to a fixed setpoint on a
    fixed schedule and has no comfort-taking at all, so it must predict gas
    use falling steeply with the rating - the opposite of the measured
    pattern. The E1 report names that as a limitation and week 2 as the place
    to fix it. This test exists so that nobody later adjusts the physics to
    make consumption fall with BER and believes they have improved it.
    """
    from baile_nua.calibration.targets import gas_per_dwelling_targets

    by_type: dict[str, dict[str, float]] = {}
    for t in gas_per_dwelling_targets(2022):
        by_type.setdefault(t.conditioned_on["dwelling_type"], {})[
            t.conditioned_on["source_ber_label"]
        ] = float(t.value)
    bands = ["A - B", "C", "D", "E", "F- G"]

    checked = 0
    for dwelling, cells in sorted(by_type.items()):
        values = [cells[b] for b in bands if b in cells]
        if len(values) < 4:
            continue
        checked += 1
        spread = (max(values) - min(values)) / min(values)
        assert spread < 0.25, (
            f"{dwelling}: gas use varies by {spread:.0%} across BER bands. "
            f"The measured spread is 4 to 7%; a larger one would mean the "
            f"table has been misread. {dict(zip(bands, values))}"
        )

    assert checked >= 3, f"only {checked} dwelling types had enough bands"

    # Across dwelling types, the ordering is strong and must hold.
    allband = {
        d: cells["All BER ratings"]
        for d, cells in by_type.items() if "All BER ratings" in cells
    }
    order = [d for d in ("apartment", "terraced", "semi-detached", "detached")
             if d in allband]
    values = [allband[d] for d in order]
    assert values == sorted(values), (
        f"gas use must increase with dwelling size: "
        f"{dict(zip(order, values))}"
    )
    assert values[-1] / values[0] > 1.5, (
        f"detached to apartment gas ratio is only {values[-1] / values[0]:.2f}; "
        f"the measured ratio is about 1.84, and dwelling size is the dominant "
        f"predictor"
    )


def test_the_electricity_and_gas_ber_axes_behave_differently():
    """DBEREL01's BER axis confounds fuel; DBERNG01's does not.

    Pinned because the two tables look interchangeable and are not: in the
    electricity table an A-rated detached house uses nearly twice the
    electricity of an F-rated one (7,979 against 4,156) because it is the one
    with the heat pump. Comparing a gas-heated simulated home against the
    electricity A-B cell would therefore be scoring it against homes that heat
    with electricity.
    """
    from baile_nua.calibration.targets import electricity_per_dwelling_targets

    by_type: dict[str, dict[str, float]] = {}
    for t in electricity_per_dwelling_targets(2022):
        by_type.setdefault(t.conditioned_on["dwelling_type"], {})[
            t.conditioned_on["source_ber_label"]
        ] = float(t.value)
    det = by_type["detached"]
    assert det["A - B"] > 1.5 * det["F- G"], (
        f"A-B detached electricity {det['A - B']} is not far above F-G "
        f"{det['F- G']}; the fuel confound that makes this axis unusable for a "
        f"gas-heated dwelling has gone, and the comparison rule should change "
        f"with it"
    )


def test_the_floor_area_target_is_a_lower_bound_and_says_so():
    from baile_nua.calibration.targets import floor_area_target

    t = floor_area_target()
    assert 60.0 <= float(t.value) <= 140.0
    assert "lower bound" in t.scope_note.lower()
    assert t.conditioned_on["tenure"].startswith("rented")


def test_the_period_mapping_covers_every_band_d02_can_emit():
    """A band the mapping has not heard of must not be dropped silently.

    The first version of the mapping omitted "2011-2015", which D02 emits, and
    it raised rather than quietly excluding those dwellings from the held-out
    comparison - which would have biased it towards whichever eras happened to
    be mapped.
    """
    from baile_nua.population.buildings import _BAND_YEARS
    from baile_nua.report.artefacts import _PERIOD_OF

    missing = set(_BAND_YEARS) - set(_PERIOD_OF)
    assert not missing, (
        f"these year_built_band values have no period mapping: "
        f"{sorted(missing)}"
    )
    # And every target period must be one the source actually publishes.
    from baile_nua.calibration.targets import gas_by_construction_targets

    published = {
        t.conditioned_on["period_of_construction"]
        for t in gas_by_construction_targets(2022)
    }
    unknown = set(_PERIOD_OF.values()) - published
    assert not unknown, (
        f"the mapping targets periods the source does not publish: "
        f"{sorted(unknown)}; published: {sorted(published)}"
    )
