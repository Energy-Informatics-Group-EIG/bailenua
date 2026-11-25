"""Deriving F1/F2 grey-box RC parameters from the BER asset rating (design 5.7).

    One grey-box RC model per building (3R2C or 4R2C, two zones: living and
    sleeping), with parameters drawn per archetype.  The reference is the asset
    rating (BER/DEAP), but operational behaviour is allowed to diverge from it.
    The performance gap is modelled, not hidden.

**The derivation chain**, so that every number traces to either a measurement or
a declared assumption:

1. The building's **BER band** comes from CSO EBA02, conditional on its dwelling
   type and year of construction (real joint data for Co. Cork).
2. The band is turned into an asset-rating primary-energy figure in kWh/m2/yr
   using the regulatory band boundaries (``data/ber_bands.yaml``, flagged [A],
   I-019), and the space-heating share of that figure by a declared assumption.
3. Multiplying by floor area gives the **asset-rating annual space heat demand**.
4. Dividing by the **measured heating degree days at Roches Point in 2022**
   (1,603 Kd at base 15.5 C, computed from the real Met Éireann series, not
   quoted) gives the whole-building **heat loss coefficient** in W/K.
5. The HLC is split into a ventilation part - ``0.33 * ACH * volume``, where 0.33
   Wh/(m3 K) is the volumetric heat capacity of air, a physical constant - and a
   fabric part, which becomes the envelope resistances.
6. Thermal capacitance comes from an areal heat capacity per square metre that
   depends on construction era, which is the one place where Irish masonry
   construction has to be represented by an assumption.

**The performance gap** (design 5.7, de Wilde) is applied as a multiplier on the
derived HLC, drawn per building: real homes lose more heat than their asset
rating implies.  It is a *parameter* of the building, so the divergence between
asset and operational behaviour is a modelled property rather than noise, and
the asset rating is kept alongside it in D02 so both can be reported.
"""

from __future__ import annotations

import dataclasses
import functools
from pathlib import Path
from typing import Any

import numpy as np
import yaml

__all__ = [
    "RCParameters",
    "EnvelopeAreas",
    "envelope_areas",
    "fabric_u_values",
    "fabric_multiplier",
    "ImplausibleFabricError",
    "BAND_ORDER",
    "AGGREGATE_TO_MID",
    "resolve_aggregate_band",
    "ber_bands",
    "band_energy_kwh_m2_yr",
    "derive_rc",
    "AIR_VOLUMETRIC_HEAT_CAPACITY",
    "AREAL_HEAT_CAPACITY_KJ_M2K",
    "GLAZING_FRACTION",
    "PARTY_WALL_FRACTION",
]

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

#: Volumetric heat capacity of air at ~20 C, Wh/(m3 K).  A physical constant
#: (1.2 kg/m3 x 1005 J/(kg K) / 3600), not an assumption.
AIR_VOLUMETRIC_HEAT_CAPACITY = 0.33

#: Thermal mass parameter by construction era, kJ/(m2 K) of floor area. [A]
#:
#: This is the SAP/DEAP "thermal mass parameter" convention: the whole
#: dwelling's effective heat capacity expressed per square metre of floor area,
#: where SAP's categories are roughly light 100, medium 250 and heavy 450.
#: Irish construction is predominantly masonry - concrete block with plaster, or
#: solid stone in the oldest stock - so it sits at the heavy end, easing toward
#: medium-heavy in newer timber-frame and insulated-cavity builds.
#:
#: The first version used 100 to 150 kJ/(m2 K), which gave whole-building time
#: constants of 6 to 18 hours. Grey-box identification on real masonry dwellings
#: reports 20 to 120 hours, so those values were wrong by roughly a factor of
#: three - they had been read as a single element's areal capacity rather than
#: the whole-dwelling parameter.
#:
#: This remains the single largest assumption in the thermal model, and the F3
#: cross-model fidelity test in design 5.7 is what would falsify it.
AREAL_HEAT_CAPACITY_KJ_M2K: dict[str, float] = {
    "pre 1919": 450.0,       # solid masonry, often stone: heavy
    "1919-1945": 440.0,
    "1946-1960": 420.0,
    "1961-1970": 400.0,
    "1971-1980": 380.0,
    "1981-1990": 350.0,
    "1991-2000": 330.0,
    "2001-2010": 300.0,
    "2011-2015": 280.0,
    "2016 or later": 250.0,  # insulated cavity and timber frame: medium-heavy
    "not stated": 350.0,
}

#: Share of the dwelling's total thermal mass that sits on the envelope node
#: rather than in the zone air and furnishings. Most of a masonry dwelling's
#: inertia is in the structure, which is what makes the envelope node the slow
#: one and the zone air the fast one.
ENVELOPE_MASS_SHARE = 0.85

#: Plausible whole-building time constant, hours, from grey-box identification
#: on real dwellings. Asserted, not assumed.
PLAUSIBLE_TIME_CONSTANT_H = (15.0, 140.0)

#: Glazed fraction of floor area, by dwelling type. [A]
GLAZING_FRACTION: dict[str, float] = {
    "detached": 0.18, "semi-detached": 0.16, "terraced": 0.14,
    "apartment": 0.13, "bedsit": 0.12,
}

#: Share of perimeter wall area that is party wall (adiabatic, no loss outside).
#:
#: This is the physical reason terraced matters, and why U18's missing
#: "Terraced" value loses information rather than merely a label. On a roughly
#: square plan with four sides, a semi-detached house shares one side, an
#: end-terrace one, and a mid-terrace two:
#:
#:   detached       0 of 4 sides   = 0.00
#:   semi-detached  1 of 4         = 0.25
#:   terraced       mix of end (1 of 4) and mid (2 of 4), weighted by the CSO
#:                  EBA02 end/mid split for Co. Cork, which is roughly 40/60
#:                  = 0.40
#:   apartment      two walls plus floor and ceiling shared = 0.55
#:
#: The first version used 0.22 for terraced, which gave a mid-terrace nearly the
#: exposed wall area of a detached house and pushed its derived specific heat
#: loss to 4.46 W/(m2 K) - caught by the plausibility assertion rather than
#: shipped.
PARTY_WALL_FRACTION: dict[str, float] = {
    "detached": 0.00, "semi-detached": 0.25, "terraced": 0.40,
    "apartment": 0.55, "bedsit": 0.55,
}

#: Share of the whole-building fabric resistance that sits between the indoor
#: air node and the envelope node (internal surface + inner leaf). [A]
R_IE_FRACTION = 0.30

#: Week 3 step 1. Take wall, roof, floor and window U-values from SEAI's
#: assessed BER distribution conditional on (era cell, BER band) instead of
#: from the ``[A]`` era table times a band multiplier capped at 0.55.
#:
#: I-048 is confirmed and quantified in v1/evidence/i048_fabric_assessed.json:
#: against about a million assessed existing dwellings the era x multiplier
#: wall is 1.913x the assessed median on old stock and 0.750x on new, a 2.6x
#: divergence that one mechanism explains - the multiplier cannot reach a
#: deeply retrofitted old house (floor 2.1 x 0.55 = 1.155 against an assessed
#: 0.25) and it penalises a modern dwelling whose fabric meets the regulations
#: whatever its band.
#:
#: The switch exists so the previous behaviour stays reachable for the
#: ablation that justifies the change, not as a configuration option.
USE_ASSESSED_FABRIC = True

#: Which elements the assessed conditional covers. The BER Research Tool
#: publishes U-values for these four; it has no door U-value, no thermal
#: bridging factor and no air-change rate, so those three terms keep the
#: era table and its multiplier and remain ``[A]``. They are the small ones,
#: and `derive_rc` reports what share of the heat-loss coefficient is sourced
#: so the claim can be checked rather than taken on trust.
ASSESSED_ELEMENTS: tuple[str, ...] = ("wall", "roof", "floor", "window")

#: The model's era labels mapped onto the assessed conditional's era cells.
#: Wide cells, because they have to hold enough assessed dwellings per band:
#: the thinnest is about 700.
_ERA_LABEL_TO_CELL: dict[str, str] = {
    "pre 1919": "pre1919",
    "1919-1945": "1919-1960",
    "1946-1960": "1919-1960",
    "1961-1970": "1961-1980",
    "1971-1980": "1961-1980",
    "1981-1990": "1981-2000",
    "1991-2000": "1981-2000",
    "2001-2010": "2001+",
    "2011-2015": "2001+",
    "2016 or later": "2001+",
}

#: Background infiltration in air changes per hour, by construction era. [A]
ACH_BASE: dict[str, float] = {
    "pre 1919": 0.85, "1919-1945": 0.80, "1946-1960": 0.70,
    "1961-1970": 0.65, "1971-1980": 0.60, "1981-1990": 0.50,
    "1991-2000": 0.42, "2001-2010": 0.35, "2011-2015": 0.28,
    "2016 or later": 0.20, "not stated": 0.55,
}

#: Storey height in metres, floor to ceiling plus structure. [A]
STOREY_HEIGHT_M = 2.6

#: Performance gap (design 5.7, de Wilde): operational heat loss divided by
#: asset-rating heat loss.  Lognormal, median above 1 because real homes
#: generally underperform their rating. [A] - risk K14 records that the Irish
#: evidence base for this is thin.
PERFORMANCE_GAP_MEDIAN = 1.15
PERFORMANCE_GAP_SIGMA = 0.18


@functools.lru_cache(maxsize=1)
def ber_bands() -> dict[str, Any]:
    return yaml.safe_load((DATA_DIR / "ber_bands.yaml").read_text(encoding="utf-8"))


def band_energy_kwh_m2_yr(band: str, u: float = 0.5) -> tuple[float, float]:
    """Asset-rating primary energy and space-heat share for a BER band.

    ``u`` in [0, 1] places the building within its band, so two C-rated homes
    are not identical - the band is a range and the position within it is part
    of the building's identity rather than a constant.

    Returns ``(primary_kwh_m2_yr, space_heat_fraction)``.
    """
    cfg = ber_bands()
    spec = cfg["bands"].get(band) or cfg["aggregates"].get(band)
    if spec is None:
        raise KeyError(
            f"unknown BER band {band!r}; known: "
            f"{sorted(cfg['bands'])} and {sorted(cfg['aggregates'])}"
        )
    lo, hi = float(spec["lo"]), float(spec["hi"])
    primary = lo + (hi - lo) * float(np.clip(u, 0.0, 1.0))
    letter = band[0].upper()
    frac = cfg["space_heat_fraction"].get(letter, 0.62)
    return primary, float(frac)


@dataclasses.dataclass
class RCParameters:
    """F1 two-zone grey-box parameters, plus what they were derived from."""

    # resistances, K/W
    r_ie: float
    r_ea: float
    r_zz: float
    r_inf: float
    # capacitances, J/K
    c_living: float
    c_sleep: float
    c_env: float
    # geometry and gains
    solar_aperture_m2: float
    vol_living_m3: float
    vol_sleep_m3: float
    ach_base: float
    heat_emitter_w: float
    # provenance
    derivation: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def time_constant_hours(self) -> float:
        """Whole-building time constant, the headline sanity check.

        Grey-box identification on real dwellings reports 20 to 120 hours; a
        value far outside that means the capacitance or the HLC is wrong.
        """
        c_total = self.c_living + self.c_sleep + self.c_env
        hlc = 1.0 / (self.r_ie + self.r_ea) + 1.0 / self.r_inf
        return c_total / hlc / 3600.0

    @property
    def hlc_w_per_k(self) -> float:
        return 1.0 / (self.r_ie + self.r_ea) + 1.0 / self.r_inf


def fabric_u_values() -> dict[str, Any]:
    return _load_fabric()


@functools.lru_cache(maxsize=1)
def _load_fabric() -> dict[str, Any]:
    return yaml.safe_load((DATA_DIR / "fabric_u_values.yaml").read_text(encoding="utf-8"))


#: Median BER band by construction era, used to decide whether a building's
#: actual band is better or worse than its era implies (and therefore whether
#: its fabric has been upgraded).  Derived from the CSO EBA02 joint table for
#: Co. Cork at run time by :func:`median_band_by_era`, so it is measured rather
#: than assumed; this ordering is only the band scale.
BAND_ORDER: tuple[str, ...] = (
    "A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3",
    "D1", "D2", "E1", "E2", "F", "G",
)
#: CSO EBA02 reports aggregated letters; map each to its mid sub-band so a band
#: from the BER data can be placed on the same scale.
AGGREGATE_TO_MID: dict[str, str] = {
    "A": "A2", "A0": "A1", "B": "B2", "C": "C2", "D": "D1", "E": "E1", "F-G": "F",
}


def resolve_aggregate_band(band: str, position: float) -> str:
    """Turn an aggregated CSO band into a definite fine band.

    CSO EBA02 publishes A1, A2, A3, B1, B2, B3 individually but aggregates C,
    D, E and F-G. The schema's ``ber_band`` enum - and the building's identity -
    needs a definite band, so the aggregate is resolved to one of its members
    using the same ``position`` already drawn to place the building within its
    band. That keeps one draw doing one job: position within the aggregate and
    position within the fine band are the same quantity.

    The validator caught this: writing "C" into D02 failed the enum check rather
    than being silently accepted, which is exactly what the schema is for.
    """
    cfg = ber_bands()
    agg = cfg["aggregates"].get(band)
    if agg is None:
        return band
    members = list(agg["members"])
    if not members:
        return band
    i = min(int(float(np.clip(position, 0.0, 0.999999)) * len(members)), len(members) - 1)
    return members[i]


def _band_index(band: str) -> int:
    b = AGGREGATE_TO_MID.get(band, band)
    try:
        return BAND_ORDER.index(b)
    except ValueError:
        raise KeyError(f"unknown BER band {band!r}") from None


def fabric_multiplier(ber_band: str, era_median_band: str) -> tuple[float, str]:
    """How much better or worse than its era this building's fabric is.

    A pre-1919 terrace rated C has clearly been retrofitted; one rated F has
    not.  Using the era U-values alone would make them identical, which would
    erase exactly the heterogeneity design R10 asks for ("homes differ in
    demographics, socio-economics, BER, age, location and DER").
    """
    cfg = _load_fabric()["ber_band_fabric_multiplier"]
    delta = _band_index(era_median_band) - _band_index(ber_band)
    if delta >= 3:
        key = "much_better"
    elif delta >= 1:
        key = "better"
    elif delta <= -3:
        key = "much_worse"
    elif delta <= -1:
        key = "worse"
    else:
        key = "typical"
    return float(cfg[key]), key


@dataclasses.dataclass
class EnvelopeAreas:
    """Envelope areas implied by floor area, storeys and dwelling type."""

    footprint_m2: float
    wall_gross_m2: float
    wall_net_m2: float
    window_m2: float
    door_m2: float
    roof_m2: float
    ground_floor_m2: float
    party_wall_m2: float
    volume_m3: float
    exposed_m2: float


def envelope_areas(
    floor_area_m2: float, storeys: int, dwelling_type: str
) -> EnvelopeAreas:
    """Geometry from floor area, on a square-plan assumption.

    A square plan minimises perimeter for a given area, so this slightly
    *under*-states wall area for the long narrow plans typical of a terrace.
    The direction of the approximation is recorded rather than corrected,
    because correcting it would need plan dimensions that no public source
    provides for Cobh.

    Party walls are adiabatic: they are the physical reason a mid-terrace loses
    less heat than a semi-detached, and the reason U18's missing "Terraced"
    value loses information rather than merely a label.
    """
    storeys = max(int(storeys), 1)
    footprint = floor_area_m2 / storeys
    side = float(np.sqrt(max(footprint, 1.0)))
    perimeter = 4.0 * side
    wall_gross = perimeter * storeys * STOREY_HEIGHT_M

    party_frac = PARTY_WALL_FRACTION.get(dwelling_type, 0.0)
    party = wall_gross * party_frac
    exposed_wall = wall_gross - party

    window = floor_area_m2 * GLAZING_FRACTION.get(dwelling_type, 0.15)
    door = 1.9 * (2.0 if dwelling_type in ("detached", "semi-detached", "terraced") else 1.0)
    window = min(window, max(exposed_wall - door - 1.0, 1.0))

    # An apartment has neither its own roof nor its own ground floor unless it
    # is a top- or ground-floor unit; averaged over the stack, a third of each.
    roof = footprint if dwelling_type not in ("apartment", "bedsit") else footprint / 3.0
    ground = footprint if dwelling_type not in ("apartment", "bedsit") else footprint / 3.0

    wall_net = max(exposed_wall - window - door, 1.0)
    return EnvelopeAreas(
        footprint_m2=footprint, wall_gross_m2=wall_gross, wall_net_m2=wall_net,
        window_m2=window, door_m2=door, roof_m2=roof, ground_floor_m2=ground,
        party_wall_m2=party, volume_m3=floor_area_m2 * STOREY_HEIGHT_M,
        exposed_m2=wall_net + window + door + roof + ground,
    )


class ImplausibleFabricError(ValueError):
    """A derived building falls outside the published heat-loss range."""


def derive_rc(
    *,
    ber_band: str,
    era_median_band: str,
    floor_area_m2: float,
    dwelling_type: str,
    year_built_band: str,
    storeys: int,
    n_bedrooms: int,
    band_position: float = 0.5,
    airtightness_factor: float = 1.0,
    hdd_annual: float | None = None,
) -> RCParameters:
    """Derive one building's F1 two-zone RC parameters, forward from U-values.

    ``hdd_annual`` is optional and used only to report the implied annual heat
    demand alongside the parameters, so the result can be compared with the BER
    asset rating.  It no longer *drives* the derivation - see
    ``data/fabric_u_values.yaml`` for why inverting the BER figure through
    degree days could not recover a fabric property.
    """
    if floor_area_m2 <= 0:
        raise ValueError(f"floor area must be positive, got {floor_area_m2}")

    cfg = _load_fabric()
    era = cfg["eras"].get(year_built_band, cfg["eras"]["not stated"])
    mult, mult_key = fabric_multiplier(ber_band, era_median_band)
    geo = envelope_areas(floor_area_m2, storeys, dwelling_type)

    # -- element U-values ----------------------------------------------------
    #
    # Wall, roof, floor and window come from SEAI's ASSESSED distribution
    # conditional on (era cell, BER band). The band multiplier is deliberately
    # NOT applied to them: the assessed conditional already depends on the
    # band, so multiplying again would count the band twice - and the
    # multiplier is the very mechanism I-048 showed to be wrong.
    #
    # Door, thermal bridging and infiltration keep the era table and the
    # multiplier, because the source publishes none of them. They stay [A].
    u: dict[str, float] = {k: era[k] * mult
                           for k in ("wall", "roof", "floor", "window", "door")}
    sourced_elements: tuple[str, ...] = ()
    fabric_source = "era table x BER-band multiplier ([A])"
    if USE_ASSESSED_FABRIC:
        from baile_nua.physics import fabric_assessed as _assessed

        cell = _ERA_LABEL_TO_CELL.get(year_built_band)
        if cell is not None:
            try:
                for element in ASSESSED_ELEMENTS:
                    u[element] = _assessed.u_for_cell(cell, ber_band, element)
                sourced_elements = ASSESSED_ELEMENTS
                fabric_source = (
                    "SEAI BER Research Tool, assessed median conditional on "
                    "(era cell, BER band); door, thermal bridging and "
                    "infiltration remain [A] from the era table"
                )
            except _assessed.AssessedFabricError:
                # An era with no published cell at any band falls back to the
                # era table rather than guessing. 'not stated' is the case
                # that reaches here.
                sourced_elements = ()

    # -- fabric transmission, element by element (the DEAP/SAP method) -------
    hlc_elements = (
        u["wall"] * geo.wall_net_m2
        + u["roof"] * geo.roof_m2
        + u["floor"] * geo.ground_floor_m2
        + u["window"] * geo.window_m2
        + u["door"] * geo.door_m2
    )
    hlc_sourced = sum(
        u[k] * {"wall": geo.wall_net_m2, "roof": geo.roof_m2,
                "floor": geo.ground_floor_m2, "window": geo.window_m2}[k]
        for k in sourced_elements
    )
    hlc_bridging = era["thermal_bridge_y"] * mult * geo.exposed_m2
    hlc_fabric = hlc_elements + hlc_bridging

    # -- ventilation and infiltration ---------------------------------------
    ach = era["ach"] * airtightness_factor * (0.85 + 0.30 * band_position)
    hlc_vent = AIR_VOLUMETRIC_HEAT_CAPACITY * ach * geo.volume_m3

    hlc = hlc_fabric + hlc_vent
    specific = hlc / floor_area_m2
    lo = cfg["plausible_specific_hlc_w_m2k"]["lo"]
    hi = cfg["plausible_specific_hlc_w_m2k"]["hi"]
    if not (lo <= specific <= hi):
        raise ImplausibleFabricError(
            f"derived specific heat loss {specific:.2f} W/(m2 K) is outside the "
            f"published plausible range [{lo}, {hi}] for a {dwelling_type} of "
            f"{floor_area_m2:.0f} m2 built {year_built_band} rated {ber_band}. "
            f"Fabric parameters are not silently accepted outside the range the "
            f"literature supports."
        )

    # -- resistances --------------------------------------------------------
    r_fabric_total = 1.0 / hlc_fabric
    r_ie = R_IE_FRACTION * r_fabric_total
    r_ea = (1.0 - R_IE_FRACTION) * r_fabric_total
    r_inf = 1.0 / max(hlc_vent, 1e-6)

    # -- zone volumes -------------------------------------------------------
    sleep_share = float(np.clip(0.20 + 0.08 * max(n_bedrooms, 1), 0.20, 0.55))
    vol_sleep = geo.volume_m3 * sleep_share
    vol_living = geo.volume_m3 - vol_sleep

    partition_area = 2.0 * float(np.sqrt(max(geo.footprint_m2, 1.0))) * STOREY_HEIGHT_M
    r_zz = 1.0 / max(partition_area * 2.0, 1.0)

    # -- capacitances -------------------------------------------------------
    areal_c = AREAL_HEAT_CAPACITY_KJ_M2K.get(
        year_built_band, AREAL_HEAT_CAPACITY_KJ_M2K["not stated"]
    )
    # The thermal mass parameter is the WHOLE dwelling's capacity, so it is
    # split across the three nodes rather than added to them: most on the
    # envelope (slow), the rest in the zone air and furnishings (fast),
    # distributed between the two zones by volume.
    c_total = areal_c * 1000.0 * floor_area_m2
    c_env = c_total * ENVELOPE_MASS_SHARE
    c_zones = c_total * (1.0 - ENVELOPE_MASS_SHARE)
    vol_frac = vol_living / max(geo.volume_m3, 1e-9)
    c_living = c_zones * vol_frac
    c_sleep = c_zones * (1.0 - vol_frac)

    # -- solar aperture -----------------------------------------------------
    # Effective aperture = glazed area x transmittance x frame factor x shading.
    solar_aperture = geo.window_m2 * 0.70 * 0.70 * 0.90

    # -- emitter sizing -----------------------------------------------------
    # Irish external design temperature is about -1 C; 21 C internal, 1.3 margin.
    heat_emitter_w = hlc * (21.0 - (-1.0)) * 1.3

    tau_h = (c_living + c_sleep + c_env) / hlc / 3600.0
    lo_t, hi_t = PLAUSIBLE_TIME_CONSTANT_H
    if not (lo_t <= tau_h <= hi_t):
        raise ImplausibleFabricError(
            f"derived time constant {tau_h:.1f} h is outside the plausible range "
            f"[{lo_t}, {hi_t}] h reported by grey-box identification on real "
            f"dwellings, for a {dwelling_type} of {floor_area_m2:.0f} m2 built "
            f"{year_built_band} rated {ber_band} (HLC {hlc:.1f} W/K)."
        )

    derivation: dict[str, Any] = {
        "method": "forward from Part L U-values and envelope areas (DEAP/SAP method)",
        "time_constant_hours": round(tau_h, 1),
        "ber_band": ber_band,
        "era_median_band": era_median_band,
        "fabric_multiplier": mult,
        "fabric_multiplier_class": mult_key,
        "u_values_used": dict(u),
        "fabric_source": fabric_source,
        "fabric_elements_sourced": list(sourced_elements),
        "fabric_sourced_share_of_hlc": (
            round(hlc_sourced / hlc, 4) if hlc > 0 else None
        ),
        "areas_m2": dataclasses.asdict(geo),
        "hlc_elements_w_per_k": round(hlc_elements, 2),
        "hlc_thermal_bridging_w_per_k": round(hlc_bridging, 2),
        "hlc_fabric_w_per_k": round(hlc_fabric, 2),
        "ach_effective": round(ach, 3),
        "hlc_ventilation_w_per_k": round(hlc_vent, 2),
        "hlc_total_w_per_k": round(hlc, 2),
        "specific_hlc_w_m2k": round(specific, 3),
        "areal_heat_capacity_kj_m2k": areal_c,
    }
    if hdd_annual:
        # Implied annual heat demand, for comparison with the BER asset rating.
        implied = hlc * hdd_annual * 24.0 / 1000.0
        derivation["implied_annual_space_heat_kwh"] = round(implied, 0)
        derivation["implied_space_heat_kwh_m2_yr"] = round(implied / floor_area_m2, 1)
        derivation["hdd_annual_measured"] = round(hdd_annual, 1)

    return RCParameters(
        r_ie=r_ie, r_ea=r_ea, r_zz=r_zz, r_inf=r_inf,
        c_living=c_living, c_sleep=c_sleep, c_env=c_env,
        solar_aperture_m2=solar_aperture,
        vol_living_m3=vol_living, vol_sleep_m3=vol_sleep,
        ach_base=ach, heat_emitter_w=heat_emitter_w,
        derivation=derivation,
    )
