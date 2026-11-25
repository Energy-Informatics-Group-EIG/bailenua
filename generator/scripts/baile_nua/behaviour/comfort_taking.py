"""U22: comfort-taking - rebound in efficient homes, prebound in poor ones.

What is being reproduced, and why it is behaviour
------------------------------------------------
DBERNG01 says something that looks impossible for a physics model: within every
dwelling type, measured gas use varies only **4 to 7%** across BER bands, and
A-B rated detached houses burn **more** gas (14,618 kWh) than F-G ones (13,292),
while varying **84%** across dwelling types. Measured consumption tracks
dwelling **size**, not fabric quality.

A thermostat at a fixed setpoint cannot produce that. Halve a dwelling's heat
loss and its space heat halves. The E1 run did exactly that and measured a
space-heat ratio of 0.43 against the published cell for 1967-99 stock and 0.19
for post-2005 - the better the fabric, the further below the real meter the
model fell, which is the signature of a missing behavioural response rather
than a physics error.

The mechanism is that people spend some of an efficiency gain on warmth rather
than on money. A better-insulated home is heated warmer, for longer, and in
more rooms; a poorly insulated one is heated less, because it costs more than
the household will pay. The first is **rebound**, the second **prebound**, and
both are decisions, not thermal properties.

D-022 is why this module exists rather than a fabric adjustment: *"Fitting the
physics to reproduce a behavioural effect would hide the gap instead of
measuring it, and would make the fabric parameters wrong for every other
purpose."* U22 restates it as a prohibition - **never tune building physics to
absorb comfort-taking** - so nothing here touches
:class:`~baile_nua.physics.archetype.ThermalParams`. What it returns is a
setpoint the occupant asks for and the hours they ask for it.

The quantity that drives it
---------------------------
Not the BER letter. The cost of a degree in a dwelling is set by how fast heat
leaves it, which is its **specific heat loss** in W/K - and that is a physical
property the model already has, from the same RC parameters the solver uses. A
dwelling with half the heat loss buys a degree for half the money.

The response is logarithmic in that cost ratio, and the reason is not
cosmetic: a household that gains a degree from halving its heat loss does not
gain two from halving it again. A linear response would hand implausible
setpoints to the best dwellings and then have to be clipped, which is a way of
discovering a model is wrong by watching it hit a limit.

Why it is split into COM-B terms
--------------------------------
Design 5.3 locates comfort-taking in COM-B, and keeping the three terms
separate is what makes the mechanism falsifiable rather than a single fitted
knob:

* **Opportunity** is the dwelling: cost per degree, from its heat loss.
* **Capability** is affordability: a household on a low income in a leaky
  dwelling prebounds hard, and the same dwelling with a comfortable income
  barely prebounds at all. This is the term that makes prebound a cost
  response rather than a fabric response.
* **Motivation** is the ``comfort`` trait the population already carries, which
  already shifts the setpoint and is left doing so.

A single knob fitted to the BER flatness would reproduce the flatness and tell
us nothing. Three terms with different drivers can disagree with the data.

Calibration and validation are kept disjoint
--------------------------------------------
The strength is set against **DBERNG01** - dwelling type x BER band - because
that is the axis the effect is defined on. It is validated on **DBERNG02** -
dwelling type x period of construction - which is declared held-out and which
nothing here is allowed to see. Design 7.1 requires the separation and the two
sources carry it in their declarations.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

__all__ = [
    "ComfortTakingSpec",
    "DEFAULT_SPEC",
    "AFFORDABILITY_BY_QUINTILE",
    "TENURE_AFFORDABILITY_SHIFT",
    "specific_loss_w_k_m2",
    "affordability",
    "comfort_shift",
]


@dataclasses.dataclass(frozen=True)
class ComfortTakingSpec:
    """The declared strengths. Set against DBERNG01, validated on DBERNG02.

    Every field is a behavioural amplitude. None of them is a thermal
    property, and that separation is the point of U22.
    """

    #: Degrees of setpoint gained per natural log unit of cost reduction. At
    #: this value a dwelling with half the stock's heat loss asks for about
    #: 1.0 K more than one at the median.
    rebound_k_per_ln_cost: float = 1.45

    #: Degrees given up per natural log unit of cost INCREASE, for a household
    #: with no affordability headroom. Larger than the rebound term because
    #: the responses are not symmetric: giving up warmth you cannot afford is
    #: forced, where taking warmth you can afford is optional.
    prebound_k_per_ln_cost: float = 2.30

    #: Share of the heating window a fully prebounding household gives up.
    #: Hours matter more than degrees in real prebound - people heat one room
    #: for two hours rather than the house for eight - so this carries more of
    #: the effect than the setpoint term does.
    prebound_max_hours_fraction: float = 0.45

    #: Share of the window a fully rebounding household adds, as a fraction of
    #: what is left unheated. Smaller than the prebound figure: there is less
    #: room to extend a window than to abandon one.
    rebound_max_hours_fraction: float = 0.30

    #: How much of the sleeping zone's heating a fully prebounding household
    #: abandons, 0 to 1.
    #:
    #: This term was missing from the first version, and the strength sweep
    #: found out: setpoint and hours alone take the BER spread from 108% to
    #: 46% and then SATURATE - pushing the amplitudes from 3x to 4x moves it
    #: not at all, because both terms clip. The residual spread is the fabric
    #: range (0.63 to 6.49 W/K/m2, a factor of ten), and no house-wide
    #: temperature reduction can flatten gas across a tenfold fabric spread.
    #:
    #: The project's own description of the mechanism had it right and the
    #: model did not: "a better-insulated home is heated warmer, longer and
    #: IN MORE ROOMS". Real Irish prebound is heating one room, not turning
    #: the whole house down a degree. Abandoning a zone removes its losses
    #: entirely rather than scaling them, which is why it can do what a
    #: setpoint shift cannot.
    prebound_max_zone_abandonment: float = 0.85

    #: Bounds on the setpoint shift, in kelvin. Not a tuning parameter - a
    #: guard, so that a mis-specified cost ratio shows up as a clipped shift
    #: in the diagnostics rather than as a 30 degC living room. PL-TEMP-01
    #: would catch the latter, and this makes it visible earlier.
    max_setpoint_shift_c: float = 2.6
    min_setpoint_shift_c: float = -3.4

    #: The stock's specific heat loss, W/K per m2, that the cost ratio is
    #: measured against. The dwelling at this value takes no shift at all.
    #:
    #: The town's MEDIAN, not its mean. The distribution is right-skewed - the
    #: town runs 0.859 to 5.642 W/K/m2 with a median of 1.813 against a mean of
    #: 2.11 - so centring on the mean would put more than half the dwellings
    #: on the rebound side and give the mechanism a net warming effect on the
    #: town rather than a redistribution across the fabric range. Comfort-
    #: taking redistributes; that is what it is.
    #:
    #: It is also the town's and not the estate's. The E1 estate's specific
    #: loss is 1.50 W/K/m2 against the town's 2.11 mean, so centring on the
    #: estate would make every ordinary Irish dwelling look like a prebound
    #: case.
    #:
    #: **Moved from 2.08 to 1.813 in week 3 step 1, and not as a new choice.**
    #: D-048 defines this as the town's median. Taking the fabric from SEAI's
    #: assessed BER distribution narrowed the town's specific loss from
    #: 0.63-6.49 W/K/m2 (factor 10.3, median 2.08) to 0.859-5.642 (factor 6.6,
    #: median 1.813), which is what I-048 predicted would happen. So the
    #: median moved and the declared rule says the reference follows it.
    #: `test_the_reference_is_the_towns_median_not_its_mean` is what caught it
    #: - the constant was stale by 0.27 W/K/m2 and the suite said so before
    #: anything was run.
    reference_specific_loss_w_k_m2: float = 1.813


#: Measured from the synthesised town, not declared: see
#: `test_the_reference_is_the_towns_median`. Recomputing it keeps the mechanism
#: centred on the population actually being simulated.
DEFAULT_SPEC = ComfortTakingSpec()


#: Affordability headroom by income quintile, 0 (none) to 1 (ample).
#:
#: Keyed on the quintile the population layer already derives from SAPS
#: socio-economic group (`_SEG_TO_QUINTILE` in `population/synthesise.py`),
#: not on a second mapping of its own. An earlier version of this module
#: carried its own SEG table, which was both a duplicate and wrong - the SAPS
#: labels are letter-prefixed ("A employers and managers"), so none of its
#: keys would have matched and every household would have taken the unknown
#: midpoint.
#:
#: Declared [A]. Ireland does publish fuel poverty - SILC carries inability to
#: afford to keep the home adequately warm - but a mapping from income
#: quintile to a heating-affordability scalar is not published, and U30's
#: sweep found nothing giving one. What is defensible is the ORDERING, which
#: is why these are spaced evenly rather than fitted: the mechanism's claim is
#: that prebound falls as means rise, and the ablation tests whether that
#: claim earns its place.
AFFORDABILITY_BY_QUINTILE: dict[int, float] = {
    1: 0.20, 2: 0.40, 3: 0.55, 4: 0.75, 5: 0.90,
}

#: Tenure moves affordability independently of income: a local-authority
#: tenant faces the same fuel bill on a lower income, and an owner without a
#: mortgage has no housing cost competing with it.
TENURE_AFFORDABILITY_SHIFT: dict[str, float] = {
    "owner-occupied no mortgage": 0.10,
    "owner-occupied with mortgage": 0.0,
    "rented from private landlord": -0.10,
    "rented from local authority": -0.25,
    "rented from voluntary body": -0.20,
    "occupied free of rent": -0.15,
}


def affordability(
    *, income_quintile: int | None, tenure: str | None,
    econ_status: str | None = None,
) -> dict[str, Any]:
    """Headroom to pay for warmth, 0 to 1, with the terms kept visible.

    Returned as a dict rather than a float so the ablation can report which
    term did the work. A mechanism whose contributions cannot be separated
    cannot be argued with.
    """
    base = AFFORDABILITY_BY_QUINTILE.get(int(income_quintile or 0))
    base_from = f"income quintile {income_quintile}"
    if base is None:
        # Unknown quintile: the midpoint, flagged, rather than an optimistic
        # or pessimistic default that would bias the whole mechanism.
        base = 0.55
        base_from = "unknown quintile, midpoint"
    shift = TENURE_AFFORDABILITY_SHIFT.get(
        str(tenure or "").strip().lower(), 0.0
    )
    status = str(econ_status or "").strip().lower()
    # Being out of work or retired on a state pension bites regardless of the
    # occupation the SEG records, which is a classification of the job
    # somebody had.
    status_shift = (
        -0.15 if status in ("unemployed", "looking for first job") else
        -0.10 if status in ("retired",) else
        -0.05 if status in ("unable to work due to illness or disability",)
        else 0.0
    )
    value = max(0.0, min(1.0, base + shift + status_shift))
    return {
        "affordability": value,
        "base": base,
        "base_from": base_from,
        "tenure_shift": shift,
        "econ_status_shift": status_shift,
    }


def comfort_shift(
    *,
    specific_loss_w_k_m2: float,
    income_quintile: int | None = None,
    tenure: str | None = None,
    econ_status: str | None = None,
    spec: ComfortTakingSpec = DEFAULT_SPEC,
) -> dict[str, Any]:
    """The setpoint and heating-hours a household asks for, and why.

    Nothing here is applied to the fabric. The caller adds
    ``setpoint_shift_c`` to the temperature the thermostat is asked for and
    scales the heating window by ``hours_multiplier``; the RC parameters are
    untouched, which is U22's condition.
    """
    reference = float(spec.reference_specific_loss_w_k_m2)
    loss = max(float(specific_loss_w_k_m2), 1e-6)
    # Positive when this dwelling is CHEAPER to heat than the stock median.
    ln_cost_advantage = math.log(reference / loss)

    aff = affordability(
        income_quintile=income_quintile, tenure=tenure,
        econ_status=econ_status,
    )
    headroom = float(aff["affordability"])

    if ln_cost_advantage >= 0.0:
        # Rebound. Taking warmth you can afford is optional, so it is scaled
        # by headroom too - a household with no slack banks the saving rather
        # than spending it on temperature.
        raw = spec.rebound_k_per_ln_cost * ln_cost_advantage * headroom
        hours_fraction = (
            spec.rebound_max_hours_fraction
            * min(ln_cost_advantage, 1.0) * headroom
        )
        # A rebounding household heats MORE rooms, which in a two-zone model
        # means it stops setting back the bedrooms. Capped at zero: there is
        # no third zone to open up.
        zone_abandonment = 0.0
        mode = "rebound"
    else:
        # Prebound. Forced, so the household with the LEAST headroom gives up
        # the most: the multiplier is (1 - headroom).
        severity = min(-ln_cost_advantage, 1.5)
        raw = -spec.prebound_k_per_ln_cost * severity * (1.0 - headroom)
        hours_fraction = -(
            spec.prebound_max_hours_fraction
            * min(severity, 1.0) * (1.0 - headroom)
        )
        # Closing rooms. The term that makes the mechanism able to flatten
        # consumption across a tenfold fabric range, because it removes a
        # zone's losses rather than scaling them down.
        zone_abandonment = (
            spec.prebound_max_zone_abandonment
            * min(severity, 1.0) * (1.0 - headroom)
        )
        mode = "prebound"

    shift = max(
        spec.min_setpoint_shift_c, min(spec.max_setpoint_shift_c, raw)
    )
    clipped = abs(shift - raw) > 1e-9
    return {
        "mode": mode,
        "setpoint_shift_c": shift,
        "setpoint_shift_before_clipping_c": raw,
        "clipped": clipped,
        "hours_multiplier": 1.0 + hours_fraction,
        "sleep_zone_heated_fraction": 1.0 - zone_abandonment,
        "zone_abandonment": zone_abandonment,
        "ln_cost_advantage": ln_cost_advantage,
        "specific_loss_w_k_m2": loss,
        "reference_specific_loss_w_k_m2": reference,
        "affordability": aff,
        "com_b": {
            "opportunity": "cost per degree, from the dwelling's specific heat loss",
            "capability": "affordability headroom, from income quintile, tenure and economic status",
            "motivation": "the comfort trait, applied separately by the caller",
        },
        "never_touches": (
            "ThermalParams. U22: never tune building physics to absorb "
            "comfort-taking (D-022). This returns a temperature asked for and "
            "a window length, both decisions."
        ),
    }


def specific_loss_w_k_m2(thermal: Any, floor_area_m2: float) -> float:
    """The dwelling's specific heat loss, W/K per m2 of floor area.

    Fabric and infiltration in parallel, with the fabric path's two
    resistances in series:

        UA = 1 / (r_ie + r_ea) + 1 / r_inf

    Defined here, once, so the mechanism and every diagnostic that reports it
    agree on the quantity. It reproduces the E1 gate report's figures - the
    town's mean comes out at 2.455 W/K/m2 against the 2.45 the report states -
    which is the check that this is the same thing the report measured.
    """
    ua = 1.0 / (float(thermal.r_ie) + float(thermal.r_ea)) \
        + 1.0 / float(thermal.r_inf)
    return ua / max(float(floor_area_m2), 1.0)
