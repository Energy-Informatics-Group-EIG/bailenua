"""Met Éireann station data, and the one weather realisation (design 6.5 rule 2).

Design 6.5 rule 2, binding:

    **One weather realisation drives everything.**  Station weather (D31) and
    true site weather (D15, GT) come from the same realisation, related by a
    downscaling and offset model (coastal exposure, elevation, shelter).
    Physics, behaviour, PV and prices all see the same weather on the same day.

So there is exactly one source of truth per simulated hour, and the observable
series is a *transformation* of it, never an independent draw.

Two stations, each with a different job (design 6.4 item 7):

=================  ==========  =======================  ==========================
Station            Number      Position                 Role
=================  ==========  =======================  ==========================
Roches Point       1075        51.793N 8.244W, 40 m     drives D15, the true site
                                                        series (GT). At the mouth
                                                        of Cork Harbour, 10 km
                                                        from Cobh, same maritime
                                                        exposure.
Cork Airport       3904        51.847N 8.486W, 155 m    D31, the observable
                                                        station series (OBS). The
                                                        "nearest official station"
                                                        a real study would use.
=================  ==========  =======================  ==========================

The 115 m elevation difference and the coastal-versus-inland contrast make the
station-to-site gap *physically real* rather than injected noise, which is what
design 6.4 item 7 asks for.

**Station identity is asserted, not assumed.**  The first attempt at this used
station 1575, which is Malin Head in Co. Donegal - 400 km away on the opposite
coast - and the file downloaded cleanly, parsed cleanly and contained entirely
plausible Irish weather (ISSUES.md I-017).  Nothing downstream would have
failed.  So :func:`read_station` checks the station name, latitude, longitude and
height embedded in each file against the expected values and refuses to return
data on a mismatch.
"""

from __future__ import annotations

import dataclasses
import functools
import io
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.sources import require

__all__ = [
    "StationSpec",
    "ROCHES_POINT",
    "CORK_AIRPORT",
    "COBH_SITE",
    "StationIdentityError",
    "read_station",
    "heating_degree_days",
]

#: Met Éireann uses -999 and blanks for "no value"; both become NaN.
_MISSING_SENTINELS = (-999.0, -999.9, 999.0)


class StationIdentityError(RuntimeError):
    """A station file is not the station it was expected to be (I-017)."""


@dataclasses.dataclass(frozen=True)
class StationSpec:
    key: str                 # source registry key
    number: int
    name: str                # as it appears in the file header
    latitude: float
    longitude: float
    height_m: float
    member: str              # the CSV inside the zip
    role: str

    def tolerance(self) -> tuple[float, float]:
        """Allowed mismatch in degrees and metres when checking identity."""
        return (0.01, 2.0)


ROCHES_POINT = StationSpec(
    key="met.roches_point.hourly", number=1075, name="ROCHES POINT",
    latitude=51.793, longitude=-8.244, height_m=40.0, member="hly1075.csv",
    role="true site driver for D15 (GT)",
)

CORK_AIRPORT = StationSpec(
    key="met.cork_airport.hourly", number=3904, name="CORK AIRPORT",
    latitude=51.847, longitude=-8.486, height_m=155.0, member="hly3904.csv",
    role="observable station series D31 (OBS)",
)


@dataclasses.dataclass(frozen=True)
class SiteSpec:
    """The simulated site.  Cobh town, on Great Island in Cork Harbour."""

    name: str = "Cobh"
    #: Centroid of Cobh's 53 Census small areas, computed from the OSi
    #: boundaries rather than looked up (see population.saps.cobh_small_areas).
    latitude: float = 51.8536
    longitude: float = -8.2989
    #: Cobh rises steeply from the waterfront; this is the mean of the built area.
    height_m: float = 25.0
    timezone: str = "Europe/Dublin"


COBH_SITE = SiteSpec()


def _parse_header(text: str) -> dict[str, Any]:
    """Pull the station identity out of a Met Éireann file header."""
    out: dict[str, Any] = {}
    for line in text.splitlines()[:6]:
        low = line.lower()
        if low.startswith("station name:"):
            out["name"] = line.split(":", 1)[1].strip()
        elif low.startswith("station height:"):
            out["height_m"] = float(
                line.split(":", 1)[1].strip().upper().replace("M", "").strip()
            )
        elif "latitude" in low and "longitude" in low:
            # "Latitude:51.793  ,Longitude: -8.244"
            parts = line.replace("Latitude", "").replace("Longitude", "")
            lat_s, lon_s = parts.split(",")
            out["latitude"] = float(lat_s.replace(":", "").strip())
            out["longitude"] = float(lon_s.replace(":", "").strip())
    return out


def _assert_identity(spec: StationSpec, header: dict[str, Any]) -> None:
    deg_tol, m_tol = spec.tolerance()
    problems = []
    got_name = str(header.get("name", "")).strip().upper()
    if got_name != spec.name.upper():
        problems.append(f"name {got_name!r} != expected {spec.name!r}")
    for field, tol, unit in (
        ("latitude", deg_tol, "deg"), ("longitude", deg_tol, "deg"),
        ("height_m", m_tol, "m"),
    ):
        got = header.get(field)
        want = getattr(spec, field)
        if got is None or abs(float(got) - want) > tol:
            problems.append(f"{field} {got} != expected {want} (tolerance {tol} {unit})")
    if problems:
        raise StationIdentityError(
            f"station file for {spec.key} (expected station {spec.number}, "
            f"{spec.name}) does not match its expected identity: "
            + "; ".join(problems)
            + ". See ISSUES.md I-017: station 1575 turned out to be Malin Head, "
              "400 km from Cobh, and the file was otherwise perfectly valid."
        )


@functools.lru_cache(maxsize=8)
def _read_station_cached(spec: StationSpec, year: int | None) -> pd.DataFrame:
    """Cached parse.  The Met Éireann files are 8 to 11 MB zipped and 600,000
    lines unzipped, and parsing one takes about 10 seconds; the weather build
    reads two of them, and the physics, PV and observation layers all read them
    again. Caching turned a 23-second ten-day build into under a second."""
    return _read_station_uncached(spec, year)


def read_station(spec: StationSpec, year: int | None = None) -> pd.DataFrame:
    """Read one station's hourly series, after asserting its identity (cached).

    The returned frame is a **copy**, so a caller mutating it cannot poison the
    cache for the next caller - which would be a particularly confusing bug,
    since the symptom would appear in an unrelated subsystem.
    """
    return _read_station_cached(spec, year).copy()


def _read_station_uncached(spec: StationSpec, year: int | None = None) -> pd.DataFrame:
    """Read one station's hourly series, after asserting its identity.

    Returns a UTC-indexed frame.  Met Éireann timestamps are already UTC (the
    header says so), which matters: reading them as local time would shift every
    hour-of-day statistic by one hour in summer and leave the DST transition
    days internally inconsistent.
    """
    path = require(spec.key)
    with zipfile.ZipFile(path) as z:
        raw = z.read(spec.member).decode("latin-1")

    header = _parse_header(raw)
    _assert_identity(spec, header)

    lines = raw.splitlines()
    hdr_idx = next(
        i for i, l in enumerate(lines)
        if l.split(",")[0].strip().lower() == "date" and len(l.split(",")) > 8
    )
    body = "\n".join(lines[hdr_idx:])
    frame = pd.read_csv(
        io.StringIO(body),
        # Several columns are named `ind` (quality indicators); pandas
        # de-duplicates them as ind, ind.1, ... which is fine - they are kept so
        # the observation model can use the publisher's own quality flags.
        na_values=[" ", "", "-999", "-999.9"],
        low_memory=False,
    )
    frame["ts"] = pd.to_datetime(
        frame["date"].str.strip(), format="%d-%b-%Y %H:%M", utc=True, errors="coerce"
    )
    frame = frame.dropna(subset=["ts"]).set_index("ts").sort_index()

    for c in frame.columns:
        if c == "date":
            continue
        frame[c] = pd.to_numeric(frame[c], errors="coerce")
        frame.loc[frame[c].isin(_MISSING_SENTINELS), c] = np.nan

    if year is not None:
        frame = frame[frame.index.year == year]
        if frame.empty:
            raise RuntimeError(
                f"{spec.name} has no rows for {year}; the file covers "
                f"{frame.index.min()} to {frame.index.max()}"
            )
    frame.attrs["station"] = dataclasses.asdict(spec)
    frame.attrs["header"] = header
    return frame


def heating_degree_days(
    temps: pd.Series, base_c: float = 15.5
) -> dict[str, float]:
    """Annual heating degree days from an hourly temperature series.

    Computed from the real Roches Point series rather than quoted, because the
    building fabric parameters in :mod:`baile_nua.physics.archetype` are derived
    from the BER asset rating by dividing out the degree days, and a recalled
    figure would put a silent systematic error into every building's heat-loss
    coefficient.

    ``base_c`` of 15.5 C is the base used by the Irish DEAP methodology and by
    Met Éireann's own published degree-day series; it is declared here as a
    parameter so it can be changed in one place and shows up in the manifest.

    Hourly degree *hours* are summed and divided by 24, which is more accurate
    than the daily-mean method for a maritime climate where the diurnal range
    straddles the base temperature.
    """
    t = pd.to_numeric(temps, errors="coerce").dropna()
    if t.empty:
        raise ValueError("no temperature data")
    deficit = (base_c - t).clip(lower=0.0)
    hdd = float(deficit.sum()) / 24.0
    by_month = (deficit.groupby(t.index.month).sum() / 24.0).to_dict()
    return {
        "base_c": base_c,
        "hdd_annual": hdd,
        "hdd_by_month": {int(k): float(v) for k, v in by_month.items()},
        "n_hours": int(len(t)),
        "coverage": float(len(t) / (365.25 * 24.0)),
        "mean_temp_c": float(t.mean()),
        "min_temp_c": float(t.min()),
        "max_temp_c": float(t.max()),
    }
