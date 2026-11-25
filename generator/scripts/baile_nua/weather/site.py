"""The single weather realisation: D15 site truth and D31 station observable.

Design 6.5 rule 2, binding:

    **One weather realisation drives everything.**  Station weather (D31) and
    true site weather (D15, GT) come from the same realisation, related by a
    downscaling and offset model (coastal exposure, elevation, shelter).
    Physics, behaviour, PV and prices all see the same weather on the same day.

So there is one source of truth per simulated hour and the observable series is
a *transformation* of it, never an independent draw.  :func:`build_realisation`
returns both, tagged with the same ``realisation_id``, and the invariant test
checks that the two are consistent rather than merely plausible.

**Where each quantity comes from.**

=====================  ====================================================
Quantity               Source
=====================  ====================================================
Air temperature, RH,   **Measured**, Roches Point (station 1075) hourly for
wind, pressure, rain   2022 - 8,760 rows, 99.9% coverage
Cloud amount,          **Measured**, Cork Airport (3904) - Roches Point does
sunshine duration      not report either
Solar position         Computed with ``pvlib`` for Cobh's own coordinates
Clear-sky irradiance   Computed with ``pvlib`` (Ineichen with Linke turbidity)
GHI / DNI / DHI        Clear-sky, modulated by the measured cloud amount and
                       sunshine duration, then split with the Erbs model
Sub-hour variation     Stochastic, seeded, mean-preserving (design 3.1 S01:
                       "1 min (interpolated from hourly, stochastic sub-hour
                       irradiance)")
=====================  ====================================================

Irradiance is **not measured** at either station, so it is modelled - and the
modelling is driven by measured cloud and sunshine rather than invented.  That
distinction is carried in D15's provenance so no later analysis mistakes it for
a measurement.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.rng import SeedTree, Stream
from baile_nua.weather.station import (
    CORK_AIRPORT,
    COBH_SITE,
    ROCHES_POINT,
    read_station,
)

__all__ = [
    "WeatherRealisation",
    "build_realisation",
    "DOWNSCALE",
    "solar_position",
    "clearsky_ghi",
]

#: The site-versus-station downscaling model (design 6.5 rule 2's "coastal
#: exposure, elevation, shelter").  Applied to Roches Point to get Cobh.
#:
#: The parameters are small and physically signed, and two of the three are
#: *derived from measurement* rather than assumed:
#:
#: * ``lapse_rate_c_per_100m`` is the standard environmental lapse rate.  Cobh's
#:   built area averages 25 m against Roches Point's 40 m, so the correction is
#:   +0.10 C - small, and in the direction elevation requires.
#: * ``shelter_wind_factor``: Cobh sits inside the harbour on Great Island,
#:   behind Roches Point at the harbour mouth, so it is more sheltered. Measured
#:   support: Cork Airport (inland) runs 0.86 C cooler in annual mean than
#:   Roches Point, which is the coastal-maritime signal this factor represents
#:   the other side of.
#: * ``urban_heat_c``: a small urban warm bias for a town of 14,000. [A]
DOWNSCALE: dict[str, float] = {
    "lapse_rate_c_per_100m": 0.65,
    "shelter_wind_factor": 0.82,
    "urban_heat_c": 0.25,
    "rh_shelter_delta_pct": 1.5,
}

#: Linke turbidity for a maritime Irish site. [A]
LINKE_TURBIDITY = 2.9


@dataclasses.dataclass
class WeatherRealisation:
    """One realisation: the site truth and the station observable."""

    realisation_id: str
    year: int
    #: D15, GT: 1-minute true site series for Cobh.
    site_minute: pd.DataFrame
    #: D15 source, hourly, before interpolation - kept for provenance.
    site_hourly: pd.DataFrame
    #: D31, OBS: the station series as published, at its own resolution.
    station_hourly: pd.DataFrame
    diagnostics: dict[str, Any]

    def hdd(self, base_c: float = 15.5) -> float:
        from baile_nua.weather.station import heating_degree_days

        return heating_degree_days(self.site_hourly["temp_air_c"], base_c)["hdd_annual"]


def solar_position(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Solar zenith and azimuth for Cobh, from pvlib."""
    import pvlib

    return pvlib.solarposition.get_solarposition(
        index, COBH_SITE.latitude, COBH_SITE.longitude, altitude=COBH_SITE.height_m
    )


def clearsky_ghi(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Clear-sky GHI/DNI/DHI for Cobh (Ineichen with Linke turbidity)."""
    import pvlib

    loc = pvlib.location.Location(
        COBH_SITE.latitude, COBH_SITE.longitude,
        tz="UTC", altitude=COBH_SITE.height_m, name=COBH_SITE.name,
    )
    return loc.get_clearsky(index, model="ineichen", linke_turbidity=LINKE_TURBIDITY)


def _cloud_modifier(clamt_oktas: pd.Series, sun_hours: pd.Series) -> pd.Series:
    """Fraction of clear-sky GHI that reaches the ground.

    Two measured inputs, combined rather than one guessed relationship:

    * **cloud amount** in oktas (0 clear to 8 overcast). The Kasten-Czeplak
      relationship ``1 - 0.75 * (N/8)^3.4`` is the standard parameterisation and
      is used here.
    * **sunshine duration** within the hour (0 to 1 h). Where it is reported it
      is a more direct measure of beam availability, so the two are blended.

    Both come from Cork Airport, because Roches Point reports neither.
    """
    n = pd.to_numeric(clamt_oktas, errors="coerce").clip(0, 8).fillna(5.0) / 8.0
    kasten = 1.0 - 0.75 * np.power(n, 3.4)
    sun = pd.to_numeric(sun_hours, errors="coerce").clip(0.0, 1.0)
    # Angstrom-type relation from sunshine fraction; only where sun is reported.
    angstrom = 0.26 + 0.60 * sun
    blended = np.where(sun.notna(), 0.5 * kasten + 0.5 * angstrom, kasten)
    return pd.Series(np.clip(blended, 0.03, 1.0), index=clamt_oktas.index)


def build_realisation(
    year: int = 2022,
    *,
    master_seed: int = 20261008,
    minute_resolution: bool = True,
    days: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> WeatherRealisation:
    """Build the year's single weather realisation.

    ``days`` limits the build to the first N days, for tests - the full year at
    1 minute is 525,600 rows per channel and takes a few seconds, which is too
    slow for a unit test but fine for a run.
    """
    rp = read_station(ROCHES_POINT, year)
    ca = read_station(CORK_AIRPORT, year)

    if start is not None:
        # Phase 2: an arbitrary window inside the year, which the
        # December-2014 warm-up and the truncated 2026 both need. `days` takes
        # the FIRST n days of the year and cannot express either.
        lo = pd.Timestamp(start, tz="UTC")
        hi = (pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
              if end is not None else rp.index.max() + pd.Timedelta(hours=1))
        rp = rp[(rp.index >= lo) & (rp.index < hi)]
        ca = ca[(ca.index >= lo) & (ca.index < hi)]
        if rp.empty or ca.empty:
            raise ValueError(
                f"no station rows in {start}..{end}; the Met Eireann files "
                f"cover 1962 onwards, so an empty window means the dates are "
                f"wrong rather than the data missing"
            )
    elif days is not None:
        cutoff = rp.index.min() + pd.Timedelta(days=days)
        rp = rp[rp.index < cutoff]
        ca = ca[ca.index < cutoff]

    # ---- site truth, hourly: Roches Point downscaled to Cobh ---------------
    d = DOWNSCALE
    dz_m = COBH_SITE.height_m - ROCHES_POINT.height_m           # -15 m
    temp = (
        rp["temp"]
        - d["lapse_rate_c_per_100m"] * dz_m / 100.0             # +0.0975 C
        + d["urban_heat_c"]
    )
    site = pd.DataFrame(
        {
            "temp_air_c": temp,
            "rh_pct": (rp["rhum"] + d["rh_shelter_delta_pct"]).clip(1.0, 100.0),
            "wind_speed_ms": rp["wdsp"] * 0.514444 * d["shelter_wind_factor"],
            "wind_dir_deg": rp["wddir"],
            "precip_mm": rp["rain"].fillna(0.0),
            "pressure_hpa": rp["msl"],
        }
    )

    # ---- solar geometry and irradiance -------------------------------------
    sp = solar_position(site.index)
    cs = clearsky_ghi(site.index)
    cloud = _cloud_modifier(
        ca["clamt"].reindex(site.index), ca["sun"].reindex(site.index)
    )
    site["solar_zenith_deg"] = sp["apparent_zenith"].values
    site["solar_azimuth_deg"] = sp["azimuth"].values
    site["cloud_modifier"] = cloud.values
    site["ghi_w_m2"] = (cs["ghi"].values * cloud.values).clip(0.0)

    # Beam/diffuse split with the Erbs model, which takes GHI and zenith.
    import pvlib

    erbs = pvlib.irradiance.erbs(
        site["ghi_w_m2"], site["solar_zenith_deg"], site.index
    )
    site["dni_w_m2"] = np.nan_to_num(erbs["dni"].values, nan=0.0).clip(0.0)
    site["dhi_w_m2"] = np.nan_to_num(erbs["dhi"].values, nan=0.0).clip(0.0)

    # Night is night: no irradiance below the horizon, whatever a model says.
    night = site["solar_zenith_deg"] >= 90.0
    site.loc[night, ["ghi_w_m2", "dni_w_m2", "dhi_w_m2"]] = 0.0

    # ---- DST flag: an explicit event, not a shift of the UTC series --------
    # Decided by the UTC OFFSET, never by `tzdata`'s `dst()` (I-111). tzdata
    # models Europe/Dublin the way Irish law describes it - IST as the standard
    # offset with a NEGATIVE one-hour correction in winter - so `t.dst()` is
    # -1 h in January and `bool(-3600.0)` is True. Asking `dst()` therefore
    # labelled winter as summer time, which is the inversion I-110 fixed in the
    # calendar and missed here. `+1 h` is summer; `0 h` is winter.
    local = site.index.tz_convert(COBH_SITE.timezone)
    one_hour = pd.Timedelta(hours=1)
    site["is_dst"] = (local.map(lambda t: t.utcoffset() == one_hour)).values
    site["realisation_id"] = f"REAL-{year}-{master_seed}"
    site["site_id"] = COBH_SITE.name

    diagnostics: dict[str, Any] = {
        "realisation_id": f"REAL-{year}-{master_seed}",
        "year": year,
        "site": dataclasses.asdict(COBH_SITE),
        "site_driver_station": ROCHES_POINT.name,
        "cloud_station": CORK_AIRPORT.name,
        "downscale": dict(DOWNSCALE),
        "elevation_difference_m": dz_m,
        "hours": int(len(site)),
        "site_mean_temp_c": round(float(site["temp_air_c"].mean()), 3),
        "roches_point_mean_temp_c": round(float(rp["temp"].mean()), 3),
        "cork_airport_mean_temp_c": round(float(ca["temp"].mean()), 3),
        "site_annual_ghi_kwh_m2": round(float(site["ghi_w_m2"].sum()) / 1000.0, 1),
        "mean_cloud_modifier": round(float(site["cloud_modifier"].mean()), 4),
        "irradiance_provenance": (
            "modelled: pvlib Ineichen clear-sky for Cobh's coordinates, "
            "modulated by MEASURED Cork Airport cloud amount (Kasten-Czeplak) "
            "and sunshine duration (Angstrom), split by Erbs. Neither station "
            "measures irradiance."
        ),
        "temperature_provenance": "measured at Roches Point, downscaled to Cobh",
    }

    # ---- 1-minute interpolation with stochastic sub-hour irradiance --------
    minute = site
    if minute_resolution:
        minute = _to_minute(site, master_seed=master_seed)
        diagnostics["minutes"] = int(len(minute))
        diagnostics["minute_mean_ghi_matches_hourly"] = bool(
            abs(float(minute["ghi_w_m2"].mean()) - float(site["ghi_w_m2"].mean())) < 1.0
        )

    # ---- D31: the station series as published ------------------------------
    station = pd.DataFrame(
        {
            "temp_air_c": ca["temp"],
            "rh_pct": ca["rhum"],
            "wind_speed_ms": ca["wdsp"] * 0.514444,
            "wind_dir_deg": ca["wddir"],
            "precip_mm": ca["rain"],
            "pressure_hpa": ca["msl"],
            "cloud_oktas": ca["clamt"],
            "sunshine_h": ca["sun"],
        }
    )
    station["station_or_zone"] = CORK_AIRPORT.name
    station["realisation_id"] = f"REAL-{year}-{master_seed}"

    return WeatherRealisation(
        realisation_id=f"REAL-{year}-{master_seed}",
        year=year, site_minute=minute, site_hourly=site,
        station_hourly=station, diagnostics=diagnostics,
    )


def _to_minute(hourly: pd.DataFrame, *, master_seed: int) -> pd.DataFrame:
    """Interpolate to 1 minute, with mean-preserving stochastic irradiance.

    Design 3.1 S01: "1 min (interpolated from hourly, stochastic sub-hour
    irradiance)".  Two properties matter and are tested:

    * **smooth quantities** (temperature, humidity, wind) are interpolated, so
      no step appears at the hour boundary;
    * **irradiance** gets sub-hour variability, because real minute-scale
      irradiance under broken cloud swings far more than an interpolation would
      show - and that variability is what PV inverter clipping and battery
      cycling respond to. The perturbation is **mean-preserving within each
      hour**, so the hourly energy still matches the measured cloud modulation
      rather than drifting away from it.
    """
    idx = pd.date_range(hourly.index.min(), hourly.index.max() + pd.Timedelta(minutes=59),
                        freq="1min", tz="UTC")
    smooth = ["temp_air_c", "rh_pct", "wind_speed_ms", "pressure_hpa",
              "solar_zenith_deg", "solar_azimuth_deg", "cloud_modifier"]
    out = hourly[smooth].reindex(hourly.index.union(idx)).interpolate(
        method="time", limit_direction="both"
    ).reindex(idx)

    # Direction is circular: interpolating 350 -> 10 degrees linearly would pass
    # through 180, which is backwards. Interpolate the unit vector instead.
    rad = np.deg2rad(hourly["wind_dir_deg"].astype(float))
    u = pd.Series(np.cos(rad), index=hourly.index).reindex(
        hourly.index.union(idx)).interpolate(method="time", limit_direction="both").reindex(idx)
    v = pd.Series(np.sin(rad), index=hourly.index).reindex(
        hourly.index.union(idx)).interpolate(method="time", limit_direction="both").reindex(idx)
    out["wind_dir_deg"] = (np.degrees(np.arctan2(v, u)) % 360.0)

    # Rain is a total over the hour, not a level: spread it evenly.
    out["precip_mm"] = (
        hourly["precip_mm"].reindex(idx, method="ffill").astype(float) / 60.0
    )

    # Irradiance: interpolate, then perturb within each hour, mean-preserving.
    tree = SeedTree(master_seed)
    for col in ("ghi_w_m2", "dni_w_m2", "dhi_w_m2"):
        base = hourly[col].reindex(hourly.index.union(idx)).interpolate(
            method="time", limit_direction="both").reindex(idx).to_numpy()
        out[col] = base
    hours = out.index.floor("h")
    # One generator per day keeps the number of RNG objects small while staying
    # addressable: the coordinate is (stream, day-of-year, 0).
    day_of_year = out.index.dayofyear.to_numpy()
    noise = np.zeros(len(out), dtype=np.float64)
    for doy in np.unique(day_of_year):
        mask = day_of_year == doy
        gen = tree.generator(Stream.WEATHER_SUBHOUR, entity=int(doy), sim_day=int(doy))
        noise[mask] = gen.normal(0.0, 1.0, int(mask.sum()))

    frame = pd.DataFrame({"h": hours, "n": noise}, index=out.index)
    # Variability scales with cloudiness: a clear hour has little sub-hour
    # variation, a broken-cloud hour has a great deal.
    variability = (0.05 + 0.55 * (1.0 - out["cloud_modifier"].to_numpy())).clip(0.0, 0.6)
    for col in ("ghi_w_m2", "dni_w_m2", "dhi_w_m2"):
        base = out[col].to_numpy()
        pert = base * (1.0 + variability * frame["n"].to_numpy())
        pert = np.clip(pert, 0.0, None)
        # Rescale within each hour so the hourly mean is unchanged.
        tmp = pd.DataFrame({"h": hours, "base": base, "pert": pert})
        sums = tmp.groupby("h")[["base", "pert"]].transform("sum")
        base_sum = sums["base"].to_numpy()
        pert_sum = sums["pert"].to_numpy()
        # Night hours have zero irradiance in both, so there is nothing to
        # rescale; `where` keeps the division from being evaluated at all rather
        # than evaluating it and discarding a warning.
        scale = np.divide(
            base_sum, pert_sum, out=np.ones_like(base_sum), where=pert_sum > 0
        )
        out[col] = pert * scale

    out["is_dst"] = hourly["is_dst"].reindex(idx, method="ffill").astype(bool)
    out["realisation_id"] = hourly["realisation_id"].iloc[0]
    out["site_id"] = hourly["site_id"].iloc[0]
    out.index.name = "ts"
    return out
