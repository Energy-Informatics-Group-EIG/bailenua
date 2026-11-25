"""The run a set of exporters is pointed at, and the state they share.

Every exporter in this package is a function of a :class:`RunContext`, and the
context is a function of two paths: the run root to read and the output root to
write.  Nothing is hard-coded to ``v1/`` - the same call exports the estate
year, the 14-day town run, or ``work/town_decade/year_YYYY/`` when it exists.

**The start date is read, never assumed.**  ``t0`` comes from the earliest
timestamp in the run's OWN Parquet parts (D16's ``ts``, D11's and D13's
``start``), floored to the day; ``n_days`` comes from the latest.  D18 is
excluded from that scan on purpose: its device clock error is modelled rather
than corrected, so its timestamps run past the end of the simulated year and
would make the run look a day longer than it was.

**The structural state is rebuilt, not re-simulated.**  D01, D02, D05-D08, D14
and D15 are all deterministic functions of the master seed, so the context
rebuilds them by calling the frozen engine's own constructors -
``synthesise_t0``, ``build_realisation``, ``build_calendar``, ``build_slice``,
``build_runner_for_slice`` - with the seed the run recorded.  No day is
stepped: the runner is built for the setpoints and comfort-taking shifts it
carries, and then left alone.
"""

from __future__ import annotations

import dataclasses
import functools
import json
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = [
    "ArtefactAbsent",
    "ExportError",
    "RunContext",
    "TIME_COLUMN",
    "T0_SCAN_DATASETS",
]


class ExportError(RuntimeError):
    """The exporter was asked for something the run cannot answer honestly."""


class ArtefactAbsent(ExportError):
    """The run does not carry the artefact a dataset is converted from.

    Distinct from :class:`ExportError` because the two mean opposite things to
    a reader of the export record: an ExportError is a FAILURE - the exporter
    could not do its job - while this is an ABSENCE, and the 14-day town run
    legitimately has one (it carries no ten-year life course, so it has no
    D03, D09 or D20 rows to convert).
    """


#: The timestamp column each already-written dataset carries.
TIME_COLUMN: dict[str, str] = {
    "D11": "start", "D13": "start", "D16": "ts",
    "D18": "ts", "D19": "interval_start",
}

#: Which of those the start date is read from.  D18 is excluded: its clock
#: error is part of the model (see the module docstring).
T0_SCAN_DATASETS: tuple[str, ...] = ("D16", "D11", "D13", "D19")


@dataclasses.dataclass
class RunContext:
    """One run's identity, geometry and lazily rebuilt t0 state."""

    run_root: Path
    out_root: Path
    #: Written under ``<out_root>/<package>/<subdir>/`` when set.  Exists so a
    #: second run's export can be kept beside a first one's without either
    #: pretending to be the other.
    subdir: str | None = None

    master_seed: int = 0
    slice_kind: str = "e1_estate"
    coupling_mode: str = "C1"
    n_homes_recorded: int = 0
    n_people_recorded: int = 0
    t0: pd.Timestamp = dataclasses.field(
        default_factory=lambda: pd.Timestamp("1970-01-01", tz="UTC"))
    n_days: int = 0
    t0_evidence: dict[str, Any] = dataclasses.field(default_factory=dict)
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)
    run_name: str = ""

    # -- construction --------------------------------------------------------

    @classmethod
    def open(
        cls, run_root: str | Path, out_root: str | Path, *,
        subdir: str | None = None, run_name: str | None = None,
    ) -> RunContext:
        run_root = Path(run_root)
        diag_path = run_root / "run_diagnostics.json"
        if not diag_path.exists():
            raise ExportError(
                f"{diag_path} does not exist, so the run's master seed and "
                f"slice kind cannot be read. Every exporter is keyed to the "
                f"seed the run recorded; guessing it would silently export a "
                f"different population from the one on disk."
            )
        diag = json.loads(diag_path.read_text(encoding="utf-8"))
        sl = diag.get("slice") or {}
        t0, n_days, evidence = _resolve_calendar(run_root)
        return cls(
            run_root=run_root,
            out_root=Path(out_root),
            subdir=subdir,
            master_seed=int(diag["master_seed"]),
            slice_kind=str(sl.get("slice_kind") or "e1_estate"),
            coupling_mode=str(diag.get("coupling_mode") or "C1"),
            n_homes_recorded=int(sl.get("n_homes") or 0),
            n_people_recorded=int(sl.get("n_people") or 0),
            t0=t0, n_days=n_days, t0_evidence=evidence,
            diagnostics=diag,
            run_name=run_name or run_root.name,
        )

    # -- geometry ------------------------------------------------------------

    @property
    def year(self) -> int:
        return int(self.t0.year)

    def day_to_timestamp(self, day_index: Any) -> Any:
        """Day index -> the UTC timestamp of that day's midnight.

        The conversion Appendix D.2 asks for: the evidence artefacts carry a
        day INDEX where the schema declares a timestamp.  ``None`` in, ``None``
        out, because an absent decision date is not day zero.
        """
        if day_index is None or (isinstance(day_index, float) and pd.isna(day_index)):
            return None
        return self.t0 + pd.Timedelta(days=int(day_index))

    def path_for(self, dataset_id: str, package: str, part: int = 0) -> Path:
        base = self.out_root / package
        if self.subdir:
            base = base / self.subdir
        return base / f"{dataset_id}_part{part:03d}.parquet"

    def provenance(self) -> dict[str, Any]:
        """The stanza every manifest this package writes carries."""
        return {
            "exported_from_run_root": str(self.run_root),
            "export_run_name": self.run_name,
            "master_seed": self.master_seed,
            "slice_kind": self.slice_kind,
            "coupling_mode": self.coupling_mode,
            "run_t0_utc": self.t0.isoformat(),
            "run_n_days": self.n_days,
            "run_t0_evidence": self.t0_evidence,
        }

    # -- rebuilt t0 state, each built once -----------------------------------

    @functools.cached_property
    def town(self) -> Any:
        import baile_nua.sources_registry  # noqa: F401  (declares the sources)
        from baile_nua.population.synthesise import synthesise_t0

        return synthesise_t0(master_seed=self.master_seed)

    @functools.cached_property
    def weather(self) -> Any:
        import baile_nua.sources_registry  # noqa: F401  (declares the sources)
        from baile_nua.weather.site import build_realisation

        return build_realisation(
            self.year, master_seed=self.master_seed,
            days=(self.n_days if self.n_days and self.n_days < 365 else None),
        )

    @functools.cached_property
    def calendar(self) -> list[Any]:
        from baile_nua.engine.calendar import build_calendar

        cal = build_calendar(self.year, weather_hourly=self.weather.site_hourly)
        if self.n_days and self.n_days < len(cal):
            cal = cal[: self.n_days]
        return cal

    @functools.cached_property
    def slice(self) -> Any:
        # The registry import comes BEFORE the engine import, not after it.
        # `engine.e1_run` imports `activity.engine`, which evaluates
        # `_LATEST_WORKDAY_WAKE` at module import and that reads the Cobh
        # small-area source. So importing the engine with an unpopulated
        # REGISTRY raises SourceError from a module-level constant, which
        # reads as "the source is not declared" when the source is declared
        # and the declaring module simply had not been imported yet. It only
        # shows when an exporter that needs the slice runs FIRST: a full
        # export_all starts at D01, which touches `town` and imports the
        # registry on the way.
        import baile_nua.sources_registry  # noqa: F401  (declares the sources)
        from baile_nua.engine.e1_run import build_slice

        sl = build_slice(
            self.town, master_seed=self.master_seed, calendar=self.calendar,
            slice_kind=self.slice_kind,
        )
        got = int(sl.diagnostics.get("n_homes") or len(sl.household_ids))
        if self.n_homes_recorded and got != self.n_homes_recorded:
            raise ExportError(
                f"the rebuilt slice has {got} homes but the run recorded "
                f"{self.n_homes_recorded}. The slice is a deterministic "
                f"function of the seed and the slice kind, so a mismatch means "
                f"this export would describe a different population from the "
                f"one on disk."
            )
        return sl

    @functools.cached_property
    def runner(self) -> Any:
        """The runner as ``run_year`` builds it, with NO day stepped.

        Built for one reason: it carries the per-household comfort-taking
        shift, which is what turns the comfort trait into the setpoint the
        thermostat was actually asked for.  Reproducing that arithmetic here
        would be a second implementation of a frozen mechanism.
        """
        import baile_nua.sources_registry  # noqa: F401  (as `slice`, above)
        from baile_nua.engine.e1_run import build_runner_for_slice

        return build_runner_for_slice(
            self.slice, self.weather, self.calendar,
            master_seed=self.master_seed,
            checkpoint_root=None,
        )

    # -- slice membership ----------------------------------------------------

    @functools.cached_property
    def household_ids(self) -> list[str]:
        return sorted(self.slice.household_ids)

    @functools.cached_property
    def building_ids(self) -> list[str]:
        return sorted(b.building_id for b in self.slice.buildings.values())

    @functools.cached_property
    def person_ids(self) -> list[str]:
        return sorted(
            p.person_id
            for people in self.slice.households.values() for p in people
        )

    @functools.cached_property
    def premises_of_building(self) -> dict[str, str]:
        return {b.building_id: b.premises_id
                for b in self.slice.buildings.values()}

    @functools.cached_property
    def building_of_premises(self) -> dict[str, str]:
        return {v: k for k, v in self.premises_of_building.items()}

    @functools.cached_property
    def household_of_building(self) -> dict[str, str]:
        return {b.building_id: hh for hh, b in self.slice.buildings.items()}


# --------------------------------------------------------------------------- #
# reading the run's own calendar off its own Parquet
# --------------------------------------------------------------------------- #

def _parts(run_root: Path, dataset_id: str) -> list[Path]:
    out: list[Path] = []
    for pkg in ("ground_truth", "observable"):
        out += sorted((run_root / pkg).glob(f"{dataset_id}_part*.parquet"))
    return out


def _resolve_calendar(run_root: Path) -> tuple[pd.Timestamp, int, dict[str, Any]]:
    """``(t0, n_days, evidence)`` read from the run's written parts.

    Raises rather than defaulting.  A default start date is the single most
    damaging thing this module could invent: every day-index conversion in
    :mod:`baile_nua.export.from_evidence` is measured from it.
    """
    import pyarrow.parquet as pq

    seen: dict[str, dict[str, str]] = {}
    lo: pd.Timestamp | None = None
    hi: pd.Timestamp | None = None
    for dataset_id in T0_SCAN_DATASETS:
        col = TIME_COLUMN[dataset_id]
        d_lo: pd.Timestamp | None = None
        d_hi: pd.Timestamp | None = None
        for path in _parts(run_root, dataset_id):
            series = pd.to_datetime(
                pq.read_table(path, columns=[col])[col].to_pandas(), utc=True)
            if series.empty:
                continue
            a, b = series.min(), series.max()
            d_lo = a if d_lo is None or a < d_lo else d_lo
            d_hi = b if d_hi is None or b > d_hi else d_hi
        if d_lo is None:
            continue
        seen[dataset_id] = {"min": d_lo.isoformat(), "max": d_hi.isoformat()}
        lo = d_lo if lo is None or d_lo < lo else lo
        hi = d_hi if hi is None or d_hi > hi else hi
    if lo is None or hi is None:
        raise ExportError(
            f"no timestamped Parquet part under {run_root}/ground_truth or "
            f"{run_root}/observable, so the run's start date cannot be read. "
            f"Scanned {list(T0_SCAN_DATASETS)}. The start date is not assumed: "
            f"without it the day-index conversions for D03, D09 and D20 have "
            f"no origin."
        )
    t0 = lo.floor("D")
    n_days = int((hi.floor("D") - t0).days) + 1
    evidence = {
        "read_from": seen,
        "t0_rule": (
            "the earliest timestamp over D16.ts, D11.start, D13.start and "
            "D19.interval_start, floored to the day"
        ),
        "n_days_rule": "the latest of the same, floored to the day, minus t0, plus one",
        "d18_excluded_because": (
            "D18's device clock error is modelled rather than corrected, so its "
            "timestamps run past the end of the simulated span"
        ),
    }
    return t0, n_days, evidence
