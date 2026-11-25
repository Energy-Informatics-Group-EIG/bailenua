"""Dated asset and occupancy events: the rest of I-054, and the I-062 fix.

:mod:`baile_nua.physics.retrofit` made a *fabric* passport event change the
building from its effective day. This module does the same for the other three
kinds of dated change WP5 produces, and in doing so fixes I-062.

**What was wrong, and it is two different faults.**

*Quantisation.* ``apply_year_to_slice`` builds the slice from the ``YearState``
snapshot taken at the **start** of a year, so a measure or a birth that falls on
day 200 of 2025 first appears in the series on day 0 of **2026**. The D20 label
carries the real onset day. A detector scored against that label is scored
against a step up to 365 days away from where the series puts it.

*Inertness.* Worse, and found by probing the series rather than reading the
code: of the four asset measures, two never reached the physics at all.
``retrofit_heat_pump`` wrote ``owned[hh]["heat_pump"]`` and
``der_smart_controls`` wrote ``owned[hh]["smart_heating_control"]``, and the
runner reads neither — it decides the heating path on
``building.heating_system`` and ``building.heating_fuel``. Seventeen of the
decade's forty-seven passport events changed nothing while being counted as
applied. Full record in I-062.

**Where the magnitudes come from.** D-072 forbids inventing them, so every one
is read from DEAP via :mod:`baile_nua.physics.deap_controls`:

=========================  ====================================================
heat-pump conversion       the dwelling's heating system becomes a heat pump
                           and its fuel becomes electricity, and the COP is
                           derated by DEAP Table 4c(4)'s **0.70** for a heat
                           pump on standard radiators without compensation.
                           That derating is the important part: a heat pump
                           dropped into an un-retrofitted house keeps radiators
                           sized for 70 degC flow, and the regulator's answer is
                           70% of rated efficiency
smart heating controls     DEAP Table 4c(4) again: load or weather compensation
                           moves the same adjustment to **0.75**, a published
                           **+7.1%**. On a *boiler* home DEAP publishes **no**
                           effect — Table 4e gives a temperature adjustment of
                           0 for every control category from "room thermostat
                           only" upward — so the effect is recorded as
                           ``no_rated_effect`` with the reason, rather than
                           being given a number this module made up
PV and battery             the same draws ``apply_year_to_slice`` uses, moved
                           to the event's day. No new quantity
occupancy change           a person arriving or leaving. No quantity at all:
                           the effect is whatever the activity engine and the
                           metabolic gains do with one more or one fewer person
=========================  ====================================================

**The honest consequence of the smart-controls finding.** Ten of the decade's
events are smart-control installs, and most land on boiler homes where DEAP
rates the change at zero. Those events now report ``no_rated_effect`` instead
of being silently counted as applied. That is not a fix for the detector
problem — a D20 label still points at a step the series does not contain — and
it is recorded as such in I-063 rather than dressed up. Inventing a saving to
make the label true would be the worse error.

**Why the runner is mutated rather than rebuilt.** The alternative is to
rebuild the slice and the runner at every event date, which would reinitialise
every household's thermal state and tank temperature mid-year — a step change
in every dwelling in the estate, caused by one dwelling's new battery. The
runner's state is plain dicts precisely so a dated event can reach into one
household and leave the rest alone, and the test asserts that no other
household's series moves.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = [
    "AssetEffect",
    "SMART_CONTROL_MEASURE",
    "apply_heat_pump_retrofit",
    "apply_smart_controls",
    "apply_pv_install",
    "apply_battery_install",
    "apply_occupancy_change",
    "recompute_derived_household_state",
    "AssetEventError",
]

#: The WP5 measure name that installs load or weather compensation.
SMART_CONTROL_MEASURE = "der_smart_controls"


class AssetEventError(RuntimeError):
    pass


@dataclasses.dataclass
class AssetEffect:
    """What one dated asset or occupancy event did, for the D03 row.

    ``changed`` is the field that matters for I-062: an event that reached the
    physics and moved nothing records ``False`` and says why in ``note``,
    instead of being counted as applied.
    """

    event_type: str
    measure: str
    building_id: str
    effective_day: int
    changed: bool
    fields_before: dict[str, Any]
    fields_after: dict[str, Any]
    source: str
    note: str = ""

    def as_record(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# --------------------------------------------------------------------------- #
# the heating system
# --------------------------------------------------------------------------- #

def apply_heat_pump_retrofit(
    *, runner: Any, hh: str, building: Any, effective_day: int,
) -> AssetEffect:
    """Convert the dwelling to a heat pump, from the event's day.

    Three things change together, because a conversion is not one field:

    * ``heating_system`` becomes ``"heat pump"`` and ``heating_fuel`` becomes
      ``"electricity"``, which is what moves the runner onto the COP path and
      takes the dwelling's space heat off the gas meter;
    * the COP is derated by DEAP Table 4c(4) for the emitter the dwelling keeps;
    * the hot-water system is rebuilt, because ``dhw_system_for`` derives it
      from the dwelling's heating fuel and a dwelling that no longer burns gas
      does not heat its water with gas either.
    """
    from baile_nua.physics import deap_controls as DC
    from baile_nua.physics import dhw as dhw_mod

    before = {
        "heating_system": getattr(building, "heating_system", None),
        "heating_fuel": getattr(building, "heating_fuel", None),
        "hp_emitter_adjustment": runner.hp_emitter_adjustment.get(hh),
    }
    if before["heating_system"] == "heat pump":
        return AssetEffect(
            event_type="asset added", measure="retrofit_heat_pump",
            building_id=building.building_id, effective_day=effective_day,
            changed=False, fields_before=before, fields_after=before,
            source=DC.SOURCE_KEY,
            note=(
                "the dwelling already had a heat pump, so the conversion is a "
                "no-op. Reported rather than counted: WP5 guards against "
                "drawing a measure a dwelling already has, so this path "
                "firing means that guard has been bypassed."
            ),
        )

    compensation = SMART_CONTROL_MEASURE in runner.wp5_measures.get(hh, set())
    adj = DC.heat_pump_emitter_adjustment(compensation=compensation)

    building.heating_system = "heat pump"
    building.heating_fuel = "electricity"
    runner.hp_emitter_adjustment[hh] = adj

    system = dhw_mod.dhw_system_for(building, has_pv=hh in runner.pv)
    if system is None:
        raise AssetEventError(
            f"{hh}: converting to a heat pump left the dwelling with no "
            f"hot-water system. dhw_system_for has no case for "
            f"heating_fuel='electricity', heating_system='heat pump'; add the "
            f"case rather than leaving the dwelling without hot water."
        )
    runner.dhw_systems[hh] = system

    after = {
        "heating_system": "heat pump", "heating_fuel": "electricity",
        "hp_emitter_adjustment": adj,
    }
    return AssetEffect(
        event_type="asset added", measure="retrofit_heat_pump",
        building_id=building.building_id, effective_day=effective_day,
        changed=True, fields_before=before, fields_after=after,
        source=DC.SOURCE_KEY,
        note=(
            f"DEAP Table 4c(4): heat pump on standard radiators "
            f"{'with' if compensation else 'without'} load or weather "
            f"compensation, efficiency adjustment {adj}. The dwelling keeps "
            f"its radiators - A-48 - which is DEAP's worst published emitter "
            f"branch and the one a fabric retrofit leaves behind. Hot-water "
            f"system rebuilt off the new fuel."
        ),
    )


def apply_smart_controls(
    *, runner: Any, hh: str, building: Any, effective_day: int,
) -> AssetEffect:
    """Install load or weather compensation, from the event's day.

    Sourced where DEAP publishes an effect and reported as having none where it
    does not, which is the whole of the I-062 lesson: the fault was never that
    a measure did nothing, it was that a measure that did nothing was counted
    as applied.
    """
    from baile_nua.physics import deap_controls as DC

    runner.wp5_measures.setdefault(hh, set()).add(SMART_CONTROL_MEASURE)
    is_heat_pump = getattr(building, "heating_system", "") == "heat pump"
    before = {"hp_emitter_adjustment": runner.hp_emitter_adjustment.get(hh)}

    if not is_heat_pump:
        return AssetEffect(
            event_type="asset added", measure=SMART_CONTROL_MEASURE,
            building_id=building.building_id, effective_day=effective_day,
            changed=False, fields_before=before, fields_after=before,
            source=DC.SOURCE_KEY,
            note=(
                "NO RATED EFFECT, and this is the source's answer rather than "
                "an omission. DEAP Table 4e gives a living-area temperature "
                "adjustment of 0 for every control category from 'room "
                "thermostat only' upward, including 'time and temperature "
                "zone control'; Table 4c(2) penalises only the ABSENCE of "
                "thermostatic control, which every dwelling here has (I-033). "
                "So on a boiler home the regulator rates this upgrade at "
                "nothing. The measure is recorded, the D03 event stands, and "
                "the series does not move. I-063 carries what that costs a "
                "detector scored against the D20 label."
            ),
        )

    adj = DC.heat_pump_emitter_adjustment(compensation=True)
    prev = runner.hp_emitter_adjustment.get(hh)
    runner.hp_emitter_adjustment[hh] = adj
    return AssetEffect(
        event_type="asset added", measure=SMART_CONTROL_MEASURE,
        building_id=building.building_id, effective_day=effective_day,
        changed=(prev != adj), fields_before=before,
        fields_after={"hp_emitter_adjustment": adj}, source=DC.SOURCE_KEY,
        note=(
            f"DEAP Table 4c(4): load or weather compensation moves a heat "
            f"pump on standard radiators from "
            f"{DC.heat_pump_emitter_adjustment(compensation=False)} to {adj}, "
            f"a published +7.1%. This is the one dwelling type where DEAP "
            f"rates better controls as worth something."
        ),
    )


# --------------------------------------------------------------------------- #
# PV and battery: the slice's own draws, moved to the event's day
# --------------------------------------------------------------------------- #

def apply_pv_install(
    *, runner: Any, hh: str, building: Any, effective_day: int, gen: Any,
) -> AssetEffect:
    """Fit a PV system, from the event's day.

    The draws are the ones ``e1_run.build_slice`` uses at t0 and
    ``apply_year_to_slice`` repeats, so a system fitted in year six comes from
    the same distribution as one fitted before the run started. ``gen`` is
    passed in rather than drawn here so the caller owns the stream coordinates.
    """
    from baile_nua.devices import der as der_mod
    from baile_nua.physics import dhw as dhw_mod

    if hh in runner.pv:
        return AssetEffect(
            event_type="asset added", measure="der_pv",
            building_id=building.building_id, effective_day=effective_day,
            changed=False, fields_before={"has_pv": True},
            fields_after={"has_pv": True}, source="e1_run.build_slice draws",
            note="the dwelling already had PV, so the install is a no-op",
        )
    kwp = float(min(max(gen.normal(4.0, 1.2), 1.5), 8.0))
    runner.pv[hh] = der_mod.PVSystem(
        capacity_kwp=kwp,
        azimuth_deg=float(min(max(gen.normal(180.0, 40.0), 90.0), 270.0)),
        tilt_deg=float(min(max(gen.normal(32.0, 6.0), 12.0), 45.0)),
        inverter_kw=min(kwp * 0.92, 5.0),
        shading_factor=float(min(max(gen.normal(0.94, 0.05), 0.70), 1.0)),
    )
    # The diverter is enabled only where there is PV to divert, so the
    # hot-water system changes when PV arrives.
    system = dhw_mod.dhw_system_for(building, has_pv=True)
    if system is not None:
        runner.dhw_systems[hh] = system
    return AssetEffect(
        event_type="asset added", measure="der_pv",
        building_id=building.building_id, effective_day=effective_day,
        changed=True, fields_before={"has_pv": False},
        fields_after={"has_pv": True, "capacity_kwp": round(kwp, 2)},
        source="e1_run.build_slice draws",
        note=(
            "the same PV draws the slice uses at t0. Hot-water system rebuilt "
            "because the immersion diverter is enabled only where there is PV."
        ),
    )


def apply_battery_install(
    *, runner: Any, hh: str, building: Any, effective_day: int, gen: Any,
) -> AssetEffect:
    """Fit a home battery, from the event's day.

    ``initialise`` builds the ``Battery`` on the household's day-0 state from
    ``building.has_battery``, so a battery that arrives mid-year has to be
    constructed here as well as flagged, or the flag would be set on a
    household whose state has no battery in it.
    """
    from baile_nua.devices import der as der_mod

    st = runner.state.get(hh)
    if getattr(building, "has_battery", False) and st is not None and st.battery:
        return AssetEffect(
            event_type="asset added", measure="der_battery",
            building_id=building.building_id, effective_day=effective_day,
            changed=False, fields_before={"has_battery": True},
            fields_after={"has_battery": True},
            source="run.initialise battery spec",
            note="the dwelling already had a battery, so the install is a no-op",
        )
    building.has_battery = True
    if st is None:
        raise AssetEventError(
            f"{hh}: a battery install reached a household with no runner "
            f"state, so initialise() has not run for it"
        )
    st.battery = der_mod.Battery(
        capacity_wh=5000.0, max_charge_w=2500.0, max_discharge_w=2500.0,
        soc=float(gen.uniform(0.3, 0.7)),
    )
    return AssetEffect(
        event_type="asset added", measure="der_battery",
        building_id=building.building_id, effective_day=effective_day,
        changed=True, fields_before={"has_battery": False},
        fields_after={"has_battery": True, "capacity_wh": 5000.0,
                      "soc": round(st.battery.soc, 4)},
        source="run.initialise battery spec",
        note=(
            "the same 5 kWh / 2.5 kW specification initialise() gives a "
            "day-0 battery, with its state of charge drawn from the install "
            "day's own coordinates rather than day 0's"
        ),
    )


# --------------------------------------------------------------------------- #
# occupancy
# --------------------------------------------------------------------------- #

def apply_occupancy_change(
    *, runner: Any, hh: str, building: Any, effective_day: int,
    arrivals: tuple[Any, ...] = (), departures: tuple[str, ...] = (),
) -> AssetEffect:
    """Add or remove people from the household, from the event's day.

    No quantity is declared here at all, which is what makes this the cleanest
    of the four: the effect is whatever one more or one fewer person does to
    the activity engine, the metabolic gains, the hot-water draws and the
    occupancy gate on the heating. A birth on day 200 used to appear on day 0
    of the following year.

    Counter-based RNG is what makes this safe. Each person's activity draws are
    keyed on their own person id, so someone arriving mid-year does not shift
    anybody else's stream - the coordinates the others visit are unchanged.
    With a sequential generator this would have perturbed the whole estate.
    """
    people = runner.households.get(hh)
    if people is None:
        raise AssetEventError(
            f"{hh}: an occupancy change reached a household the runner does "
            f"not have"
        )
    before = tuple(p.person_id for p in people)
    leaving = set(departures)
    kept = [p for p in people if p.person_id not in leaving]
    unknown = leaving - set(before)
    new = [p for p in arrivals if p.person_id not in {q.person_id for q in kept}]
    runner.households[hh] = sorted(kept + list(new), key=lambda p: p.person_id)
    after = tuple(p.person_id for p in runner.households[hh])
    return AssetEffect(
        event_type="occupancy change", measure="occupancy",
        building_id=building.building_id, effective_day=effective_day,
        changed=(after != before),
        fields_before={"n_occupants": len(before), "person_ids": list(before)},
        fields_after={"n_occupants": len(after), "person_ids": list(after)},
        source="WP5 life course (D09 events)",
        note=(
            f"{len(new)} arrived, {len(leaving - unknown)} left"
            + (f"; {sorted(unknown)} were named as leaving but were not "
               f"resident, which is a life-course bookkeeping error rather "
               f"than an occupancy change" if unknown else "")
        ),
    )


# --------------------------------------------------------------------------- #
# derived state
# --------------------------------------------------------------------------- #

def recompute_derived_household_state(*, runner: Any, hh: str, building: Any) -> dict[str, Any]:
    """Re-derive what a dated event invalidates but does not itself set.

    Two things in the runner are computed once from the dwelling's fabric and
    then held as standing state, and a fabric event leaves both stale:

    * the **comfort shift**, which is a function of the dwelling's specific
      heat loss. After a retrofit the dwelling's cost per degree falls, so the
      household's prebound should fall with it. Leaving it stale means the
      retrofit changes the fabric and not the household's response to it,
      which is half an event.
    * the **hot-water system**, whose standing losses depend on the dwelling.

    Returns what it changed, so the caller can put it in the D03 record rather
    than have it happen invisibly.
    """
    from baile_nua.behaviour import comfort_taking as comfort_mod
    from baile_nua.physics import dhw as dhw_mod

    out: dict[str, Any] = {}
    if runner.comfort_taking:
        loss = comfort_mod.specific_loss_w_k_m2(
            runner.thermal[hh], getattr(building, "floor_area_m2", 0.0)
        )
        prev = runner.comfort_shift.get(hh) or {}
        runner.comfort_shift[hh] = comfort_mod.comfort_shift(
            specific_loss_w_k_m2=loss,
            income_quintile=runner.income_quintile.get(hh),
            tenure=getattr(building, "tenure", None),
            spec=runner.comfort_spec,
        )
        out["comfort_shift"] = {
            "specific_loss_w_k_m2": round(loss, 4),
            "setpoint_shift_c_before": prev.get("setpoint_shift_c"),
            "setpoint_shift_c_after":
                runner.comfort_shift[hh].get("setpoint_shift_c"),
            "hours_multiplier_before": prev.get("hours_multiplier"),
            "hours_multiplier_after":
                runner.comfort_shift[hh].get("hours_multiplier"),
        }
    system = dhw_mod.dhw_system_for(building, has_pv=hh in runner.pv)
    if system is not None:
        runner.dhw_systems[hh] = system
        out["dhw_system_rebuilt"] = True
    return out
