"""Passport events that change the physics from their date (I-054, week 3 step 1).

WP5's ten-year life course produces fabric retrofits and extensions, writes a
D03 passport event for each, and — until now — did not touch the building. 45%
of the building changes the decade recorded were absent from the series (8
fabric retrofits and 13 extensions of 47 passport events), so a detector scored
against those D20 labels scored a false negative through no fault of its own.

This module makes a passport event change the fabric **from its effective
day**, which is what the schema means by a dated event: the building has one
state before and another after, and the version in D03 is the boundary.

**The U-values are published, not chosen.** That matters because the fabric is
already derived from a tuning-exposed source (I-058) and a retrofit magnitude
picked to move the gas ratio would be the same mistake twice.

*Fabric retrofit.* Wall goes to DEAP Table S3's **filled-cavity** value for
the dwelling's DEAP age band — 0.6 W/m2K for every band A to G, which is the
regulator's own statement of what insulating a cavity achieves. Roof goes to
DEAP Table S4's value for the insulation depth, and the depth is the one
declared quantity here.

*Extension.* The added fabric meets the current regulations, so its U-values
are DEAP Table S2's band L row — roof 0.20, wall 0.21, floor 0.21. The
**area** added is the declared quantity.

What stays ``[A]``, with the reason:

===========================  =============================================
loft insulation depth        DEAP publishes the U-value for each depth
                             (Table S4) but not what depth a retrofit
                             installs. 300 mm is the current grant
                             standard; the U-value that follows, 0.13, is
                             DEAP's.
extension floor area share   no published distribution of Irish extension
                             sizes was found; 0.18 of the original floor
                             area is declared.
which measures a "retrofit"  a scope choice, not a quantity: this models a
comprises                    cavity-and-attic retrofit, which is what the
                             Irish grant schemes mostly fund. Windows and
                             floors are left alone.
===========================  =============================================

**Why not simply raise the BER band.** It was the first design and it is
circular in a subtle way: the fabric is derived from the assessed conditional
*keyed on the band*, so moving the band moves the fabric by whatever the
assessed population happens to show, which is a correlation between band and
fabric rather than the effect of insulating a wall. Taking the wall to DEAP's
published filled-cavity value says what the measure does.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from baile_nua.physics.rc import ThermalParams

__all__ = [
    "RETROFIT_LOFT_DEPTH_MM",
    "EXTENSION_FLOOR_AREA_SHARE",
    "RetrofitEffect",
    "fabric_retrofit_u_values",
    "extension_u_values",
    "apply_fabric_retrofit",
    "apply_extension",
    "RetrofitError",
]

#: ``[A]``. DEAP Table S4 publishes the roof U-value for each loft-insulation
#: depth; it does not publish what depth a retrofit installs. 300 mm is the
#: depth the current Irish grant schemes specify, and DEAP's U-value for
#: ">= 300" is 0.13 W/m2K — so the physical quantity is sourced and only the
#: depth is declared.
RETROFIT_LOFT_DEPTH_MM = 300

#: ``[A]``. No published distribution of Irish domestic extension sizes was
#: found. Declared as a share of the original floor area.
EXTENSION_FLOOR_AREA_SHARE = 0.18


class RetrofitError(RuntimeError):
    pass


@dataclasses.dataclass
class RetrofitEffect:
    """What one passport event did to the fabric, for the D03 row."""

    event_type: str
    building_id: str
    effective_day: int
    u_before: dict[str, float]
    u_after: dict[str, float]
    hlc_before_w_per_k: float
    hlc_after_w_per_k: float
    floor_area_before_m2: float
    floor_area_after_m2: float
    parameters_changed: dict[str, Any]
    source: str

    @property
    def hlc_ratio(self) -> float:
        return (self.hlc_after_w_per_k / self.hlc_before_w_per_k
                if self.hlc_before_w_per_k else float("nan"))


def fabric_retrofit_u_values(build_year: int) -> dict[str, float]:
    """Wall and roof U-values after a cavity-and-attic retrofit, from DEAP.

    Wall: Table S3's filled-cavity row for the dwelling's age band.
    Roof: Table S4's value for :data:`RETROFIT_LOFT_DEPTH_MM`.
    """
    from baile_nua.physics import deap_appendix_s as S

    band = S.band_for_year(int(build_year))
    tables = S.appendix_s()
    filled = tables["S3_walls"]["300mm filled cavity"]
    by_depth = tables["S4_roof_by_insulation_mm"]
    key = f">={RETROFIT_LOFT_DEPTH_MM}"
    if key not in by_depth:
        key = str(RETROFIT_LOFT_DEPTH_MM)
    if key not in by_depth:
        raise RetrofitError(
            f"DEAP Table S4 has no entry for {RETROFIT_LOFT_DEPTH_MM} mm; "
            f"published depths are {sorted(by_depth)}"
        )
    return {"wall": float(filled[band]), "roof": float(by_depth[key])}


def extension_u_values() -> dict[str, float]:
    """An extension's fabric meets current regulations: DEAP Table S2, band L."""
    from baile_nua.physics import deap_appendix_s as S

    rows = {r["band"]: r for r in S.appendix_s()["S2_regulations"]}
    if "L" not in rows:
        raise RetrofitError(
            "DEAP Table S2 has no band L row, so the current-regulations "
            "U-values for new fabric cannot be read."
        )
    r = rows["L"]
    return {"wall": float(r["wall"]), "roof": float(r["roof"]),
            "floor": float(r["floor"])}


def _hlc(tp: ThermalParams) -> float:
    return 1.0 / (tp.r_ie + tp.r_ea) + 1.0 / tp.r_inf


def _rescale_fabric(tp: ThermalParams, factor: float) -> ThermalParams:
    """Scale the fabric conductance by ``factor``, leaving infiltration alone.

    The two fabric resistances are in series and their split is a declared
    fraction (``R_IE_FRACTION``), so scaling both by the same amount changes
    the conductance without changing where the mass sits — which is what a
    fabric upgrade does and an airtightness upgrade does not.
    """
    if factor <= 0:
        raise RetrofitError(f"fabric factor must be positive, got {factor}")
    return dataclasses.replace(
        tp, r_ie=tp.r_ie / factor, r_ea=tp.r_ea / factor,
    )


def apply_fabric_retrofit(
    *, tp: ThermalParams, building: Any, effective_day: int,
) -> tuple[ThermalParams, RetrofitEffect]:
    """Insulate the cavity and the attic, from the event's day.

    The fabric conductance is scaled by the ratio the two published U-values
    imply over the dwelling's own wall and roof areas. Scaling rather than
    rebuilding the RC parameters keeps the thermal mass, the zone split and
    the solar aperture exactly as they were: a cavity fill and a loft roll
    change transmission, not the building's geometry or its mass.
    """
    from baile_nua.physics import fabric_assessed as FA
    from baile_nua.physics.archetype import envelope_areas

    geo = envelope_areas(building.floor_area_m2, building.storeys,
                         building.dwelling_type)
    before = {
        el: FA.u_for(building.build_year, building.ber_band, el)
        for el in ("wall", "roof")
    }
    after = fabric_retrofit_u_values(building.build_year)
    # Only an improvement: a dwelling already better than the published
    # retrofit value is left alone rather than made worse by "retrofitting" it.
    after = {el: min(after[el], before[el]) for el in after}

    area = {"wall": geo.wall_net_m2, "roof": geo.roof_m2}
    delta = sum((after[el] - before[el]) * area[el] for el in after)
    hlc_before = _hlc(tp)
    fabric_before = 1.0 / (tp.r_ie + tp.r_ea)
    fabric_after = max(fabric_before + delta, 0.05 * fabric_before)
    tp_after = _rescale_fabric(tp, fabric_after / fabric_before)
    effect = RetrofitEffect(
        event_type="retrofit_fabric", building_id=building.building_id,
        effective_day=effective_day, u_before=before, u_after=after,
        hlc_before_w_per_k=round(hlc_before, 3),
        hlc_after_w_per_k=round(_hlc(tp_after), 3),
        floor_area_before_m2=building.floor_area_m2,
        floor_area_after_m2=building.floor_area_m2,
        parameters_changed={
            "rc_r_ie": "scaled", "rc_r_ea": "scaled",
            "u_wall": after["wall"], "u_roof": after["roof"],
        },
        source=(
            f"DEAP Table S3 filled-cavity wall for age band "
            f"{__import__('baile_nua.physics.deap_appendix_s', fromlist=['x']).band_for_year(int(building.build_year))}"
            f" and Table S4 roof at {RETROFIT_LOFT_DEPTH_MM} mm"
        ),
    )
    return tp_after, effect


def apply_extension(
    *, tp: ThermalParams, building: Any, effective_day: int,
) -> tuple[ThermalParams, RetrofitEffect]:
    """Add floor area built to current regulations, from the event's day.

    An extension does two opposite things and both are modelled: it adds
    envelope, which adds loss, and the added envelope is far better than the
    dwelling's own, which dilutes the specific loss. Reporting only the first
    would make every extension look like a pure penalty.
    """
    from baile_nua.physics.archetype import envelope_areas

    share = EXTENSION_FLOOR_AREA_SHARE
    area_before = float(building.floor_area_m2)
    area_after = area_before * (1.0 + share)
    geo_before = envelope_areas(area_before, building.storeys,
                                building.dwelling_type)
    geo_after = envelope_areas(area_after, building.storeys,
                               building.dwelling_type)
    u_new = extension_u_values()
    added = {
        "wall": geo_after.wall_net_m2 - geo_before.wall_net_m2,
        "roof": geo_after.roof_m2 - geo_before.roof_m2,
        "floor": geo_after.ground_floor_m2 - geo_before.ground_floor_m2,
    }
    delta = sum(u_new[el] * max(added[el], 0.0) for el in u_new)
    hlc_before = _hlc(tp)
    fabric_before = 1.0 / (tp.r_ie + tp.r_ea)
    tp_after = _rescale_fabric(tp, (fabric_before + delta) / fabric_before)
    # The added volume raises the infiltration path's conductance in
    # proportion, because infiltration scales with volume.
    vol_ratio = geo_after.volume_m3 / max(geo_before.volume_m3, 1e-9)
    tp_after = dataclasses.replace(
        tp_after,
        r_inf=tp_after.r_inf / vol_ratio,
        c_living=tp_after.c_living * vol_ratio,
        vol_living_m3=tp_after.vol_living_m3 * vol_ratio,
    )
    effect = RetrofitEffect(
        event_type="extension", building_id=building.building_id,
        effective_day=effective_day, u_before={}, u_after=u_new,
        hlc_before_w_per_k=round(hlc_before, 3),
        hlc_after_w_per_k=round(_hlc(tp_after), 3),
        floor_area_before_m2=round(area_before, 1),
        floor_area_after_m2=round(area_after, 1),
        parameters_changed={
            "floor_area_m2": round(area_after, 1),
            "rc_r_ie": "scaled", "rc_r_ea": "scaled", "rc_r_inf": "scaled",
            "rc_c_living": "scaled", "rc_vol_living_m3": "scaled",
        },
        source=(
            f"DEAP Table S2 band L (current regulations) for the added "
            f"fabric; area share {share} is [A]"
        ),
    )
    return tp_after, effect
