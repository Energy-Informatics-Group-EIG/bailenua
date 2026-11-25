"""DEAP Tables 4c and 4e: what a heating *system* change does, extracted not chosen.

I-062 found that two of WP5's five building measures were counted as applied
and changed the energy series not at all: ``retrofit_heat_pump`` set
``owned[hh]["heat_pump"]``, which the runner never reads, and
``der_smart_controls`` set a key that appears nowhere else in the tree. Seven
and ten events of the decade's forty-seven, reported as applied.

Wiring them up needs a magnitude, and a magnitude is exactly what D-072 says
may not be invented: it "must come from a source ... or be flagged ``[A]`` with
a search record", and never chosen to move U31. So this module reads the
numbers out of the regulatory methodology, the same way
:mod:`baile_nua.physics.deap_appendix_s` reads the fabric defaults.

What DEAP publishes, and it is more specific than "a heat pump saves energy":

==============  ==============================================================
Table 4c(4)     the heat pump's efficiency **adjustment for the emitter it is
                connected to** — 1.0 on underfloor or warm air, **0.85** on
                fan-coil or low-temperature radiators, and **0.70** on
                standard radiators with no compensation, rising to **0.75**
                with load or weather compensation
Table 4c(2)     the boiler's efficiency adjustment for poor control —
                **0.95** for no thermostatic control of room temperature,
                0.95 for no boiler interlock
Table 4e        the **living-area temperature adjustment** by control type:
                **+0.6 degC** with no time or thermostatic control, **0** for
                every control category from "room thermostat only" upward,
                and **-0.15 degC** for a delayed-start thermostat
==============  ==============================================================

**Three consequences worth stating before the code, because two of them are
unwelcome and the third is the point.**

*A retrofit heat pump on existing radiators is derated by 0.70.* That is the
single most important number here. A heat pump dropped into an un-retrofitted
Irish house keeps that house's radiators, which were sized for 70 degC flow;
DEAP's answer is that the system runs at 70% of its rated efficiency. Modelling
the retrofit without it would make every heat-pump conversion look far better
than the regulator says it is, and the dwellings WP5 converts are mostly old
stock.

*Smart controls have no rated effect on a boiler home.* Table 4e gives a
temperature adjustment of **0** for control categories 1, 2 and 3 alike —
"programmer + room thermostat", "programmer + room thermostat + TRVs" and
"time and temperature zone control" are all 0 — and Table 4c(2) penalises only
the *absence* of thermostatic control, which every dwelling in this model
already has (the I-033 closed-loop thermostat). So within DEAP, upgrading a
boiler home's controls changes the rating by nothing. That is reported rather
than papered over: see :data:`SMART_CONTROLS_HAS_NO_RATED_BOILER_EFFECT`.

*Smart controls have a sourced effect on a heat-pump home.* Table 4c(4) says
load or weather compensation moves the adjustment from 0.70 to 0.75 — a
**+7.1%** efficiency gain, published, on exactly the homes where modern
controls are actually installed. So the measure is not inert after all; it is
inert on the wrong dwellings, and conditioning it on the heating system is what
the source supports.

**What is still ``[A]``**, and it is a scope question rather than a quantity:
which emitter a converted dwelling ends up with. This module takes the
conservative published branch — standard radiators, because a fabric retrofit
does not replace the radiators — and that choice is flagged, not hidden.
"""

from __future__ import annotations

import functools
import re

__all__ = [
    "SOURCE_KEY",
    "PAGES",
    "RETROFIT_KEEPS_STANDARD_RADIATORS",
    "SMART_CONTROLS_HAS_NO_RATED_BOILER_EFFECT",
    "ExtractionError",
    "tables",
    "heat_pump_emitter_adjustment",
    "boiler_control_efficiency_adjustment",
    "control_temperature_adjustment",
]

#: The declared source these tables come from.
SOURCE_KEY = "seai.deap.manual_4_2_7"

#: Zero-based page indices, checked by the extractor rather than trusted.
PAGES: dict[str, int] = {"table_4c": 192, "table_4e": 194}

#: ``[A]``, registered as A-48. A heat pump retrofitted into an existing
#: dwelling is assumed to keep that dwelling's standard radiators, which is
#: DEAP's **worst** published emitter branch (0.70 rather than 0.85 or 1.0).
#: Declared this way deliberately: a fabric retrofit does not replace
#: radiators, and of the three published branches this is the one that cannot
#: flatter the measure.
RETROFIT_KEEPS_STANDARD_RADIATORS = True

#: Not an assumption — a finding, and it belongs next to the code that acts on
#: it. DEAP publishes no rating effect for improving a boiler home's controls
#: beyond the room thermostat the model already gives every dwelling. Asserted
#: by ``test_deap_controls.py`` against the extracted table, so if a future
#: DEAP version introduces one, the suite says so instead of this comment
#: quietly going stale.
SMART_CONTROLS_HAS_NO_RATED_BOILER_EFFECT = True


class ExtractionError(RuntimeError):
    """The manual did not yield the table in the shape it must have."""


@functools.lru_cache(maxsize=1)
def _pages() -> list[str]:
    from pathlib import Path

    from pypdf import PdfReader

    root = Path(__file__).resolve().parents[3]
    pdf = root / "sources" / "seai" / "DEAP_Manual_4_2_7.pdf"
    if not pdf.exists():
        raise ExtractionError(
            f"{SOURCE_KEY} is not fetched: {pdf} is absent, so the control "
            f"adjustments cannot be read from their source. Fetch the source "
            f"rather than hard-coding the numbers."
        )
    return [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]


def _value_after(text: str, phrase: str, *, within_lines: int = 4) -> float:
    """The first standalone number at or after ``phrase``.

    The manual wraps a long row's label over three lines and leaves its value
    alone on a fourth, so a single-line regex finds nothing. Reading forward a
    bounded number of lines handles both layouts; a row whose value is further
    away than that has changed shape and raises rather than guessing.
    """
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if phrase not in ln:
            continue
        for j in range(i, min(i + within_lines + 1, len(lines))):
            nums = re.findall(r"(?<![\d.])(\d\.\d{1,2})(?![\d])", lines[j])
            if nums:
                return float(nums[0])
        raise ExtractionError(
            f"found {phrase!r} in the DEAP manual but no value within "
            f"{within_lines} lines of it; the table's layout has changed"
        )
    raise ExtractionError(
        f"{phrase!r} does not appear on the expected DEAP page; either the "
        f"page index in PAGES is wrong or the manual version has changed"
    )


def _signed_value_after(text: str, phrase: str) -> float:
    """A Table 4e temperature adjustment, which may be ``+0.6`` or ``-0.15``."""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if phrase not in ln:
            continue
        for j in range(i, min(i + 3, len(lines))):
            m = re.search(r"([+-]\d\.\d{1,2})", lines[j])
            if m:
                return float(m.group(1))
            # A row whose adjustment is exactly zero prints a bare "0" in the
            # column, which is a value and not a missing one.
            if re.search(r"\s0\s", lines[j]):
                return 0.0
        raise ExtractionError(
            f"found {phrase!r} in Table 4e but could not read its temperature "
            f"adjustment column"
        )
    raise ExtractionError(f"{phrase!r} does not appear on the Table 4e page")


@functools.lru_cache(maxsize=1)
def tables() -> dict[str, dict[str, float]]:
    """Extract Tables 4c(2), 4c(4) and 4e, shape-checked.

    Every value this model uses is read here and nowhere else, so a DEAP
    version that changes one of them fails the suite rather than silently
    disagreeing with the code's comments.
    """
    pages = _pages()
    p4c = pages[PAGES["table_4c"]]
    p4e = pages[PAGES["table_4e"]]
    for want, page, where in (
        ("Table 4c: Efficiency adjustment factors", p4c, "table_4c"),
        ("Table 4e: Heating system controls", p4e, "table_4e"),
    ):
        if want not in page:
            raise ExtractionError(
                f"PAGES[{where!r}] = {PAGES[where]} does not carry {want!r}; "
                f"the manual's pagination has changed"
            )

    hp = {
        "underfloor_or_warm_air": _value_after(
            p4c, "Heat pump with underfloor heating or warm air heat pump"),
        "standard_radiators_no_compensation": _value_after(
            p4c, "Heat pump with standard radiators without load or weather"),
        "standard_radiators_with_compensation": _value_after(
            p4c, "Heat pump with standard radiators and load or weather"),
        "fan_coil_or_low_temperature": _value_after(
            p4c, "Heat pump with fan coil or low temperature radiators"),
    }
    # The ordering is the physics: a worse emitter cannot score better, and
    # compensation cannot make a system worse. If the extraction mis-reads a
    # column this is what catches it.
    if not (hp["standard_radiators_no_compensation"]
            < hp["standard_radiators_with_compensation"]
            < hp["fan_coil_or_low_temperature"]
            <= hp["underfloor_or_warm_air"]):
        raise ExtractionError(
            f"Table 4c(4) came out non-monotonic in emitter quality, so a "
            f"column was mis-read: {hp}"
        )
    if not 0.5 <= hp["standard_radiators_no_compensation"] <= 0.9:
        raise ExtractionError(
            f"Table 4c(4)'s standard-radiator adjustment came out "
            f"{hp['standard_radiators_no_compensation']}, outside any "
            f"plausible range for an efficiency derating"
        )

    boiler = {
        "no_thermostatic_control_of_room_temperature": _value_after(
            p4c, "No thermostatic control of room temperature"),
        "no_boiler_interlock": _value_after(p4c, "No boiler interlock"),
    }
    for k, v in boiler.items():
        if not 0.8 <= v < 1.0:
            raise ExtractionError(
                f"Table 4c(2) {k} came out {v}; a penalty for poor control "
                f"must be below 1.0 and above 0.8"
            )

    ctrl = {
        "no_time_or_thermostatic_control": _signed_value_after(
            p4e, "No time or thermostatic control of room temperature"),
        "programmer_no_room_thermostat": _signed_value_after(
            p4e, "Programmer, no room thermostat"),
        "room_thermostat_only": _signed_value_after(p4e, "Room thermostat only"),
        "programmer_plus_room_thermostat": _signed_value_after(
            p4e, "Programmer + room thermostat "),
        "time_and_temperature_zone_control": _signed_value_after(
            p4e, "Time and temperature zone control"),
    }
    # The finding this module reports: every control category from a room
    # thermostat upward is published at zero. Checked, not asserted in prose.
    for k in ("room_thermostat_only", "programmer_plus_room_thermostat",
              "time_and_temperature_zone_control"):
        if ctrl[k] != 0.0:
            raise ExtractionError(
                f"Table 4e gives {k} a temperature adjustment of {ctrl[k]}, "
                f"not 0. SMART_CONTROLS_HAS_NO_RATED_BOILER_EFFECT and the "
                f"module docstring are now wrong and must be revised against "
                f"the document."
            )
    if ctrl["no_time_or_thermostatic_control"] <= 0.0:
        raise ExtractionError(
            f"Table 4e gives no-control a temperature adjustment of "
            f"{ctrl['no_time_or_thermostatic_control']}; it must be positive "
            f"- an uncontrolled dwelling runs warmer, not cooler"
        )

    return {
        "T4c4_heat_pump_emitter": hp,
        "T4c2_boiler_control": boiler,
        "T4e_temperature_adjustment_c": ctrl,
    }


def heat_pump_emitter_adjustment(*, compensation: bool) -> float:
    """DEAP Table 4c(4) for a heat pump on the dwelling's existing radiators.

    ``compensation`` is whether load or weather compensation is fitted, which
    is what this model's ``der_smart_controls`` measure installs. The two
    values are the published 0.70 and 0.75, so the measure's effect is DEAP's
    arithmetic rather than a declared saving.
    """
    hp = tables()["T4c4_heat_pump_emitter"]
    return (hp["standard_radiators_with_compensation"] if compensation
            else hp["standard_radiators_no_compensation"])


def boiler_control_efficiency_adjustment(
    *, thermostatic_control: bool = True, boiler_interlock: bool = True,
) -> float:
    """DEAP Table 4c(2). Returns 1.0 for a dwelling with adequate control.

    Present for completeness and for the test that pins the finding: every
    dwelling in this model has a closed-loop thermostat (I-033), so this
    returns 1.0 for all of them and improving the controls cannot move it.
    """
    t = tables()["T4c2_boiler_control"]
    if not thermostatic_control:
        return t["no_thermostatic_control_of_room_temperature"]
    if not boiler_interlock:
        return t["no_boiler_interlock"]
    return 1.0


def control_temperature_adjustment(control: str = "programmer_plus_room_thermostat") -> float:
    """DEAP Table 4e's living-area temperature adjustment, in degrees C."""
    t = tables()["T4e_temperature_adjustment_c"]
    if control not in t:
        raise ExtractionError(
            f"{control!r} is not a Table 4e control type; published types are "
            f"{sorted(t)}"
        )
    return t[control]
