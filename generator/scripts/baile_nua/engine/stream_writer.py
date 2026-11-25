"""Streams one estate-year to Parquet, one dataset at a time.

Why a writer at all, rather than building frames and calling
:func:`baile_nua.io.write_dataset` once: a year of 50 homes is 26.3 million
home-minutes, and D18 alone is about 85 million rows at the estate's device
mix.  Holding that in pandas would need tens of gigabytes, and the benchmark
would then measure a configuration the full town could never run in.  So each
day's rows are appended to a per-dataset buffer and flushed monthly, and the
benchmark measures the streaming run.

**What is deliberately NOT written, and why.**  Three D16 fields have no
per-minute model in E1's F1 physics:

``dhw_tank_c``
    E1 has no domestic hot water tank. The immersion heater is an appliance
    with a load signature, not a thermal store, so there is no tank
    temperature to report. Writing the setpoint would be inventing a
    measurement.

``ach_effective``
    The F1 model ventilates at the fabric's base air-change rate plus an
    occupancy term; it has no window-opening behaviour, so "effective" and
    "base" are the same number. It is written, and the equality is the point:
    anything that looks for behavioural ventilation in E1 will correctly find
    none.

``rh_living_pct``
    Carried through from the initial state unchanged. The F1 model has no
    moisture balance. Written as a constant so that it is visibly constant.

A reader cannot tell a missing model from a missing column, so the first is
left null and the other two are written flat, and all three are recorded in the
run's own diagnostics.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.edge.export import EXPORT_CONFIGS, build_export
from baile_nua.io import write_dataset
from baile_nua.observation.era import (
    METER_ERA_CHANNELS,
    METER_ERA_INTERVAL_S,
    Era,
    build_era_map,
    home_facts_from_slice,
)
from baile_nua.observation.sensors import TIER_DEVICES, observe_channel
from baile_nua.rng import SeedTree
from baile_nua.schema.access import package_for

__all__ = ["StreamWriter", "UNMODELLED_D16_FIELDS", "hetus_code_for",
           "d10_frame", "interval_mean_held"]

MINUTES_PER_DAY = 1440

#: D16 fields with no per-minute model, and what is written instead.
#:
#: `dhw_tank_c` left this list at U25. It was "left null: E1 has no hot water
#: tank, only an immersion load", and it now carries the modelled cylinder
#: temperature at the epoch resolution, from `physics/dhw.py`.
UNMODELLED_D16_FIELDS: dict[str, str] = {
    "ach_effective": "the fabric base rate PLUS the purge ventilation the "
                     "solver applied; F1 still has no occupant "
                     "window-opening behaviour, so above the purge threshold "
                     "this is a thermostat on the air change rate rather than "
                     "a person at a window (I-032)",
    "rh_living_pct": "written constant: F1 has no moisture balance",
}

#: How often each dataset's buffer is flushed, in simulated days.
FLUSH_EVERY_DAYS = 30


@functools.lru_cache(maxsize=64)
def hetus_code_for(activity: str) -> str:
    """D10's ``hetus_code``: the ACL00 code(s) the activity's target comes from.

    Read straight off :data:`baile_nua.activity.hetus.ACTIVITY_CODES`, which is
    the table the duration targets are drawn from and whose every label is
    checked against the registered ACL00 codelist by ``mapping_audit()``.  A
    modelled activity may draw on several codes (``laundry`` is AC331 Laundry
    plus AC332 Ironing), so several are joined with ``+`` in the table's own
    order rather than one being picked as primary - picking one would publish a
    mapping the engine does not use.  Nothing is invented and nothing is
    recomputed here.
    """
    from baile_nua.activity.hetus import ACTIVITY_CODES

    spec = ACTIVITY_CODES.get(activity)
    if spec is None:
        raise KeyError(
            f"activity {activity!r} has no entry in ACTIVITY_CODES, so D10 "
            f"has no HETUS code to report for it. The engine draws every "
            f"activity's duration from that table, so an activity missing "
            f"from it is a model bug, not a writer one."
        )
    return "+".join(code for code, _weight in spec["hetus"])


def d10_frame(
    rows: list[dict[str, Any]], *, sim_day: int, minute_index: Any,
) -> pd.DataFrame:
    """One day of activity intervals as a D10 frame.

    ``rows`` is :attr:`DayResult.activity_rows`: the intervals the activity
    engine generated for the day, flattened in sorted household order and
    already carrying the ``location_id`` the day resolved for each one.

    A module-level function rather than a block inside ``add_day`` so that the
    mapping from an interval to D10's ten fields can be tested against the
    schema without a simulated run behind it.
    """
    last = MINUTES_PER_DAY - 1
    return pd.DataFrame({
        # Deterministic from the day and the position in the day's
        # sorted-household flattening, exactly as D11's presence_id is. No
        # draw, and no counter carried between days.
        "activity_id": [
            f"AC-{sim_day:05d}-{i:06d}" for i in range(len(rows))
        ],
        "person_id": [r["person_id"] for r in rows],
        # An interval that ends at midnight is stamped 23:59, which is the
        # convention D11 and D13 already use: `minute_index` is the day's own
        # minute index and has no 1,440th entry.
        "start": minute_index[[min(r["start_min"], last) for r in rows]],
        "end": minute_index[[min(r["end_min"], last) for r in rows]],
        "activity_code": [r["activity"] for r in rows],
        "hetus_code": [hetus_code_for(r["activity"]) for r in rows],
        # Null where the interval has no place: an `in_transit` interval is on
        # the road network and there is nothing to name. D11 records the same
        # quantity the same way. Inventing the dwelling for a travelling
        # person would be a false statement about where they were.
        "location_id": [r["location_id"] for r in rows],
        "zone": [r["zone"] for r in rows],
        "joint_with": [r["joint_with"] for r in rows],
        "trigger": [r["trigger"] for r in rows],
        "deliberated": [r["deliberated"] for r in rows],
    })

#: D16 is written at the C1 network epoch rather than per minute.
#:
#: 1-minute building state for 50 homes over a year is 26.3 million rows of 15
#: columns to no purpose: the thermal time constants are 15 to 140 hours, so a
#: 15-minute sample loses nothing of the dynamics, and 15 minutes is the epoch
#: the rest of the C1 coupling already runs on. The 1-minute step is kept where
#: it matters, inside the solver and in the device and observation layers.
D16_EPOCH_MINUTES = 15


class StreamWriter:
    """Accumulates rows per dataset and flushes them to Parquet periodically."""

    def __init__(
        self, out_root: Path, *, master_seed: int,
        omit_datasets: frozenset[str] = frozenset(),
        d18_era_gating: bool = False,
    ) -> None:
        """``omit_datasets`` drops named datasets from the written package.

        ``d18_era_gating`` turns on the per-home observability eras of
        ``observation/era.py``: no D18 before a home's smart-meter install date,
        30-minute import and export between that and its PARA//EL enrolment
        date, and the full 1-minute device mix only from enrolment.

        Default **False**, for the same reason ``omit_datasets`` defaults empty:
        every existing artefact - the published estate-year included - was
        written ungated, and must keep reproducing byte for byte. Gating is a
        property of the run that asked for it, not something a later phase
        retrofits onto an earlier package. It changes D18 and nothing else; the
        proof of that is ``scripts/prove_2_3_switch.py``.

        Default empty, so every existing caller writes exactly what it wrote
        before. The ten-year life course (WP5) omits D18 - the 1-minute
        observation series, 69% of a year's bytes - because no plausibility
        check reads it: the checks read D16 and D19 only. That is not a
        weakening of the suite, and it is not asserted here either: the
        ten-year runner requires ZERO ``NO_DATA`` outcomes from the suite, so
        if omitting a dataset did starve a check the acceptance test fails.
        """
        self.gt = Path(out_root) / "ground_truth"
        self.obs = Path(out_root) / "observable"
        self.gt.mkdir(parents=True, exist_ok=True)
        self.obs.mkdir(parents=True, exist_ok=True)
        self.tree = SeedTree(master_seed)
        self.master_seed = int(master_seed)
        self.omit = frozenset(omit_datasets)
        self.d18_era_gating = bool(d18_era_gating)
        #: Built on the first day from the run's own slice, so the era map
        #: covers exactly the homes the run holds and the realised share
        #: reproduces the sourced curve at whatever scope N the run is.
        self._era: Any | None = None
        #: Home-days by era, for the run's diagnostics. A gated run has to be
        #: able to say how much of D18 it declined to write and why.
        self._era_home_days: dict[str, int] = {
            e.value: 0 for e in Era
        }
        self._buf: dict[str, list[dict[str, Any]]] = {}
        self._d18: dict[str, list[Any]] = {
            "ts": [], "value": [], "quality": [], "provenance": [], "const": [],
        }
        self._d18_rows = 0
        self._part: dict[str, int] = {}
        self._written: list[Path] = []
        self._rows: dict[str, int] = {}
        #: S11 asset-register lookups, derived once from the built network.
        self._net_assets: dict[str, Any] | None = None
        #: The DSO connection register is written ONCE: the LV topology is
        #: built once per run and does not change within it, so repeating
        #: 1,092 membership rows every epoch would publish the same register
        #: 35,040 times a year.
        self._register_written = False

    # -- accumulation --------------------------------------------------------

    def add_day(self, day: Any, result: Any, runner: Any, sl: Any) -> None:
        """Turn one day's result into rows for every dataset it feeds."""
        date = pd.Timestamp(day.date).tz_localize("UTC")
        idx = pd.date_range(date, periods=MINUTES_PER_DAY, freq="1min", tz="UTC")
        bid_to_hh = {b.building_id: hh for hh, b in sl.buildings.items()}

        # ---- D13 appliance cycles (GT) -----------------------------------
        for c in result.cycles:
            self._add("D13", {
                "cycle_id": c.cycle_id, "asset_id": c.asset_id,
                "building_id": c.building_id,
                "start": idx[min(c.start_min, MINUTES_PER_DAY - 1)],
                "end": idx[min(c.end_min, MINUTES_PER_DAY - 1)],
                "programme": c.programme, "signature_id": c.signature_id,
                "signature_seed": c.signature_seed, "energy_wh": c.energy_wh,
                "peak_w": c.peak_w,
                "caused_by_activity_id": c.caused_by_activity_id,
                "flexible": c.flexible, "shifted_by_min": c.shifted_by_min,
            })

        # ---- D10 activities (GT) -----------------------------------------
        #
        # Buffered as ONE FRAME PER DAY rather than as a row dict per
        # interval. D10 is the highest-volume ground-truth dataset in the
        # package - the estate-year recorded 1,431,287 intervals for 147
        # people, which is about 80,000 rows a day at town scale and 2.4
        # million held between flushes - and a list of 2.4 million ten-key
        # dicts is several times the memory of the same rows as columns.
        # D18 is accumulated as columns for the same reason.
        if result.activity_rows:
            self._add_frame(
                "D10", d10_frame(result.activity_rows, sim_day=day.sim_day,
                                 minute_index=idx))

        # ---- D11 presence (GT), for the days it is collected -------------
        for i, row in enumerate(result.presence_rows):
            self._add("D11", {
                "presence_id": f"PR-{day.sim_day:05d}-{i:06d}",
                "person_id": row["person_id"],
                "start": idx[min(row["start_min"], MINUTES_PER_DAY - 1)],
                "end": idx[min(row["end_min"], MINUTES_PER_DAY - 1)],
                "location_kind": row["location_kind"],
                "location_id": row["location_id"], "zone": row["zone"],
            })

        # ---- D16 building state (GT), at the C1 epoch ---------------------
        step = D16_EPOCH_MINUTES
        sub = idx[::step]
        for bid, ser in sorted(result.series.items()):
            b = sl.buildings[bid_to_hh[bid]]
            tp = sl.thermal[bid_to_hh[bid]]
            # The SAME incident series the solver used, carried on the result
            # rather than recomputed here. Recomputing it is how D16 came to
            # publish a solar gain the solver never saw - the writer used the
            # global horizontal irradiance while the solver used the glazing
            # plane, so the published energy balance did not describe the run.
            solar_w = ser["solar_incident_w_m2"] * float(tp.solar_aperture_m2)
            n = len(sub)
            frame = {
                "ts": sub,
                "building_id": [bid] * n,
                "temp_living_c": _epoch_mean(ser["temp_living_c"], step),
                "temp_sleep_c": _epoch_mean(ser["temp_sleep_c"], step),
                "temp_env_c": _epoch_mean(ser["temp_env_c"], step),
                "rh_living_pct": np.full(n, 55.0),
                "co2_living_ppm": _epoch_mean(ser["co2_living_ppm"], step),
                "co2_sleep_ppm": _epoch_mean(ser["co2_sleep_ppm"], step),
                "dhw_tank_c": _epoch_mean(ser["dhw_tank_c"], step),
                "heat_delivered_w": _epoch_mean(ser["heat_delivered_w"], step),
                "internal_gain_w": _epoch_mean(ser["internal_gain_w"], step),
                "solar_gain_w": _epoch_mean(solar_w, step),
                "ach_effective": _epoch_mean(ser["ach_effective"], step),
                "occupants_living": np.round(
                    _epoch_mean(ser["occupants_living"], step)
                ).astype(int),
                "occupants_sleep": np.round(
                    _epoch_mean(ser["occupants_sleep"], step)
                ).astype(int),
            }
            self._add_frame("D16", pd.DataFrame(frame))

        # ---- D18 observations (OBS) --------------------------------------
        day_date = date.date()
        for bid, ser in sorted(result.series.items()):
            b = sl.buildings[bid_to_hh[bid]]
            # Phase 12. Which era this home is in on this day decides whether
            # it has D18 at all, and if so on which channels at which interval.
            # Ungated, `era` is None and every branch below is the old one.
            era = None
            device_age = 2.0
            interval_s = phase_min = None
            if self.d18_era_gating:
                home = self._era_map(sl).homes.get(b.premises_id)
                era = Era.NONE if home is None else home.era_on(day_date)
                self._era_home_days[era.value] += 1
                if era is Era.NONE:
                    # Nothing is fitted. Not a gap, not a missing-data flag:
                    # there is no device, so there is no row to be missing.
                    continue
                # The device's age is measured from its install date rather
                # than held at the ungated run's flat 2.0 years, because a
                # calibration drift of two years on a meter exchanged
                # yesterday is a statement about a device that did not exist.
                device_age = max(
                    (day_date - home.install_date).days / 365.25, 0.0
                )
            net = ser["net_w"]
            truth_for = {
                "import_w": np.clip(net, 0.0, None),
                "export_w": np.clip(-net, 0.0, None),
                "ct_circuit": ser["appliance_w"],
                "temp": ser["temp_living_c"],
                "rh": np.full(MINUTES_PER_DAY, 55.0),
                "co2": ser["co2_living_ppm"],
                "pir": ser["occupied"],
                "inverter_w": ser["pv_w"],
                "bess_soc": ser["bess_soc_pct"],
                "charger_w": ser["ev_w"],
            }
            if era is Era.METER_30MIN:
                # Two channels, and they carry the INTERVAL MEAN rather than
                # an instantaneous sample: the programme's data service
                # publishes half-hourly consumption, so a 1-minute spot
                # reading stamped at the half hour would not close an energy
                # balance and would be a tell. A-100.
                channels: tuple[str, ...] = METER_ERA_CHANNELS
                interval_s, phase_min = METER_ERA_INTERVAL_S, 0
                truth_for = {
                    c: interval_mean_held(truth_for[c], interval_s // 60)
                    for c in channels
                }
            else:
                channels = TIER_DEVICES[b.sensor_tier]
            for channel in channels:
                truth = truth_for[channel]
                if not np.isfinite(truth).any():
                    continue        # the home has no such device fitted
                device_id = f"DEV-{b.premises_id}-{channel}"
                r = observe_channel(
                    truth, channel_family=channel, device_id=device_id,
                    seed_tree=self.tree, sim_day=day.sim_day,
                    device_age_years=device_age,
                    interval_s=interval_s, phase_min=phase_min,
                )
                keep = np.isfinite(r.value)
                if not keep.any():
                    continue
                # Columns, not a DataFrame.
                #
                # D18 is about 180,000 rows a day at this estate's device mix,
                # arriving as 162 separate channel series. Building a DataFrame
                # per channel and concatenating 4,860 of them per flush cost
                # several times the whole physics, occupancy and device
                # simulation it was recording. The columns are accumulated as
                # arrays and assembled once per flush instead, and the five
                # constant columns are held as (value, length) pairs rather
                # than as 1,440 copies of the same string.
                n_keep = int(keep.sum())
                self._d18["ts"].append(
                    idx[keep] + pd.to_timedelta(r.ts_offset_s[keep], unit="s")
                )
                self._d18["value"].append(r.value[keep])
                self._d18["quality"].append(
                    np.asarray(r.quality, dtype=object)[keep]
                )
                self._d18["provenance"].append(
                    np.asarray(r.provenance, dtype=object)[keep]
                )
                self._d18["const"].append(
                    (device_id, b.premises_id, channel, b.sensor_tier,
                     _unit(channel), n_keep)
                )
                self._d18_rows += n_keep

        # ---- D19 edge exports (OBS), all four U20 configurations ----------
        for name, cfg in sorted(EXPORT_CONFIGS.items()):
            if cfg.aggregate_over == "estate":
                net = sum(
                    ser["net_w"] for _bid, ser in sorted(result.series.items())
                )
                estate_id = sorted({b.estate_id for b in sl.buildings.values()})[0]
                self._add_frame("D19", build_export(
                    premises_id=f"EST-AGG-{estate_id}", minute_index=idx,
                    net_import_w=np.clip(net, 0.0, None),
                    net_export_w=np.clip(-net, 0.0, None),
                    config=cfg, estate_id=estate_id,
                ).reset_index(drop=True))
                continue
            for bid, ser in sorted(result.series.items()):
                b = sl.buildings[bid_to_hh[bid]]
                net = ser["net_w"]
                self._add_frame("D19", build_export(
                    premises_id=b.premises_id, minute_index=idx,
                    net_import_w=np.clip(net, 0.0, None),
                    net_export_w=np.clip(-net, 0.0, None),
                    config=cfg,
                ).reset_index(drop=True))

        if (day.sim_day + 1) % FLUSH_EVERY_DAYS == 0:
            self.flush()

    def _era_map(self, sl: Any) -> Any:
        """The run's era map, built once from its own slice.

        Built here rather than passed in so that no call site has to know the
        era model exists: the writer already holds the slice on every day, and
        the map is a pure function of the master seed and the slice's premises
        ids.  Built on the FIRST day and then reused, so a run whose slice is
        evolved between years by WP5's life course keeps the install dates it
        started with - a meter is not re-exchanged because a household moved.
        """
        if self._era is None:
            self._era = build_era_map(
                home_facts_from_slice(sl), master_seed=self.master_seed
            )
        return self._era

    def era_report(self) -> dict[str, Any]:
        """What the run should record about its own D18 gating.

        ``{"d18_era_gating": False}`` for an ungated run, which is the honest
        answer and is what makes a gated and an ungated package distinguishable
        from their diagnostics alone.
        """
        if not self.d18_era_gating:
            return {"d18_era_gating": False}
        out: dict[str, Any] = {
            "d18_era_gating": True,
            "home_days_by_era": dict(self._era_home_days),
        }
        if self._era is not None:
            out.update(self._era.diagnostics())
        return out

    def add_network_day(
        self, day: Any, d17_rows: list[dict[str, Any]], tn: Any, sl: Any,
    ) -> None:
        """Buffer one day of solved network state: D17 (GT) and its OBS view.

        ``d17_rows`` is what :func:`baile_nua.network.lv.d17_rows` already
        produced on each coupling epoch of this day and the run then dropped,
        keeping only a count.  Nothing is computed here: the GT frame is those
        rows, and the observable view is a PROJECTION of them - the same
        powers, with the per-element voltage and loading left behind and the
        asset register's ratings and membership attached.

        BN-1.  What the observable view is and is not is argued in
        ``schema/datasets.yaml`` under ``D17_aggregate``.  The two refusals
        that matter here:

        * no ``voltage_pu``.  :func:`lv.assert_voltage_is_not_a_claim` always
          raises, because the LV topology is a declared assumption - A-49,
          whose quantities and sweep entry live in ``network/lv.py`` - and
          voltage drop
          is a line integral along exactly the declared span.  A DSO
          measurement column of per-unit voltages would present that
          assumption as an observation.
        * no ``loading_pct``.  Per-element loading is ground truth and stays
          there.  The ratings and the measurements are both published because
          BN-1 names them; their ratio is not.
        """
        if not d17_rows:
            return

        # ---- D17 network state (GT) --------------------------------------
        # Already exactly D17's ten declared fields, in the schema's own
        # order; `lv.d17_rows` is written against the schema.
        self._add_frame("D17", pd.DataFrame(d17_rows))

        if "D17_aggregate" in self.omit:
            return

        assets = self._network_assets(tn, sl)
        obs: list[dict[str, Any]] = []

        # ---- the connection register (OBS), once per run ------------------
        if not self._register_written:
            as_at = pd.Timestamp(day.date).tz_localize("UTC")
            for premises_id, sub, feeder in assets["register"]:
                obs.append({
                    "record_kind": "connection_register",
                    "ts": as_at,
                    "premises_id": premises_id,
                    "substation_ref": sub,
                    "feeder_ref": feeder,
                    "transformer_rated_kva": None,
                    "feeder_rated_a": None,
                    "p_kw_measured": None,
                    "q_kvar_measured": None,
                })
            self._register_written = True

        # ---- the feeder-head and substation measurements (OBS) -----------
        trafo_kva = assets["transformer_rated_kva"]
        feeder_a = assets["feeder_rated_a"]
        sub_of_feeder = assets["substation_of_feeder"]
        for r in d17_rows:
            eid, kind = r["element_id"], r["element_kind"]
            if kind == "transformer":
                obs.append({
                    "record_kind": "substation",
                    "ts": r["ts"],
                    "premises_id": None,
                    "substation_ref": eid,
                    "feeder_ref": None,
                    "transformer_rated_kva": trafo_kva.get(eid),
                    "feeder_rated_a": None,
                    "p_kw_measured": r["p_kw"],
                    "q_kvar_measured": r["q_kvar"],
                })
            elif kind == "feeder":
                obs.append({
                    "record_kind": "feeder_head",
                    "ts": r["ts"],
                    "premises_id": None,
                    "substation_ref": sub_of_feeder[eid],
                    "feeder_ref": eid,
                    "transformer_rated_kva": None,
                    "feeder_rated_a": feeder_a.get(eid),
                    "p_kw_measured": r["p_kw"],
                    "q_kvar_measured": r["q_kvar"],
                })
            # A `connection` element would be per-MPRN power, which the
            # aggregate view does not publish; nothing produces one today and
            # if something starts to, it is dropped here rather than leaked.
        if obs:
            self._add_frame("D17_aggregate", pd.DataFrame(obs))

    def _network_assets(self, tn: Any, sl: Any) -> dict[str, Any]:
        """The operator's asset and connection registers, derived once.

        Both ratings are CATALOGUE values of the pandapower standard types the
        network is built from - the transformer's ``sn_mva`` and the feeder
        cable's ``max_i_ka`` - so neither is a number written in this project.
        """
        if self._net_assets is not None:
            return self._net_assets
        net = tn.net
        premises_of = {
            b.building_id: b.premises_id for b in sl.buildings.values()
        }
        register = []
        for bid in sorted(tn.assignment):
            sub, feeder = tn.assignment[bid]
            pid = premises_of.get(bid)
            if pid is None:
                # A connection the slice does not hold a premises for has no
                # MPRN to register; skipped rather than given a fabricated one.
                continue
            register.append((pid, sub, feeder))
        sub_of_feeder: dict[str, str] = {}
        for bid, (sub, feeder) in tn.assignment.items():
            sub_of_feeder[feeder] = sub
        self._net_assets = {
            "register": register,
            "transformer_rated_kva": {
                sub: float(net.trafo.at[ti, "sn_mva"]) * 1000.0
                for sub, ti in tn.trafo_by_substation.items()
            },
            "feeder_rated_a": {
                f: float(net.line.at[li, "max_i_ka"]) * 1000.0
                for f, li in tn.head_line_by_feeder.items()
            },
            "substation_of_feeder": sub_of_feeder,
        }
        return self._net_assets

    # -- buffering -----------------------------------------------------------

    def _add(self, dataset_id: str, row: dict[str, Any]) -> None:
        self._buf.setdefault(dataset_id, []).append(row)

    def _add_frame(self, dataset_id: str, frame: pd.DataFrame) -> None:
        self._buf.setdefault(dataset_id, []).append(frame)

    def _assemble_d18(self) -> pd.DataFrame | None:
        """Build the one D18 frame for this flush from the accumulated columns."""
        if not self._d18["const"]:
            return None
        repeat = np.array([c[5] for c in self._d18["const"]], dtype=np.int64)
        frame = pd.DataFrame({
            "device_id": np.repeat([c[0] for c in self._d18["const"]], repeat),
            "premises_id": np.repeat([c[1] for c in self._d18["const"]], repeat),
            "channel": np.repeat([c[2] for c in self._d18["const"]], repeat),
            # Already UTC-aware: concatenating the DatetimeIndex objects
            # preserves the zone, so localising again is an error rather than a
            # no-op. np.concatenate would strip it, which is why the index
            # objects are appended rather than their values.
            "ts": (
                self._d18["ts"][0].append(self._d18["ts"][1:])
                if len(self._d18["ts"]) > 1 else self._d18["ts"][0]
            ),
            "value": np.concatenate(self._d18["value"]),
            "quality": np.concatenate(self._d18["quality"]),
            "tier": np.repeat([c[3] for c in self._d18["const"]], repeat),
            "provenance": np.concatenate(self._d18["provenance"]),
            "unit": np.repeat([c[4] for c in self._d18["const"]], repeat),
        })
        for k in self._d18:
            self._d18[k] = []
        return frame

    def flush(self) -> None:
        """Write every buffer and clear it."""
        if "D18" in self.omit:
            # Drop the accumulated columns rather than leaving them to grow:
            # omitting the dataset has to omit its MEMORY too, or a ten-year
            # run holds every minute of every year it was told not to write.
            for _k in self._d18:
                self._d18[_k] = []
            d18 = None
        else:
            d18 = self._assemble_d18()
        if d18 is not None and len(d18):
            part = self._part.get("D18", 0)
            path = self.obs / f"D18_part{part:03d}.parquet"
            write_dataset(d18, "D18", path, extra_meta={
                "part": part, "rows": int(len(d18)), "streamed": True,
            })
            self._written.append(path)
            self._rows["D18"] = self._rows.get("D18", 0) + len(d18)
            self._part["D18"] = part + 1
        for dataset_id in sorted(self._buf):
            if dataset_id in self.omit:
                self._buf[dataset_id] = []
                continue
            items = self._buf[dataset_id]
            if not items:
                continue
            if isinstance(items[0], pd.DataFrame):
                frame = pd.concat(items, ignore_index=True)
            else:
                frame = pd.DataFrame(items)
            part = self._part.get(dataset_id, 0)
            # Which package a dataset belongs in is its access class, and
            # the schema is the single source of truth for that (D-006).
            root = self.obs if package_for(dataset_id) == "observable" else self.gt
            path = root / f"{dataset_id}_part{part:03d}.parquet"
            write_dataset(frame, dataset_id, path, extra_meta={
                "part": part, "rows": int(len(frame)),
                "streamed": True,
                "unmodelled_fields": (
                    UNMODELLED_D16_FIELDS if dataset_id == "D16" else {}
                ),
            })
            self._written.append(path)
            self._rows[dataset_id] = self._rows.get(dataset_id, 0) + len(frame)
            self._part[dataset_id] = part + 1
            self._buf[dataset_id] = []

    def close(self) -> None:
        self.flush()

    # -- reporting -----------------------------------------------------------

    def storage_report(self) -> dict[str, Any]:
        by_dataset: dict[str, dict[str, Any]] = {}
        total = 0
        for path in self._written:
            # On "_part", not on "_": D17_aggregate is a dataset id with an
            # underscore in it, and splitting on the first one filed its
            # bytes under D17.
            ds = path.name.split("_part")[0]
            size = path.stat().st_size
            man = path.with_suffix(path.suffix + ".manifest.json")
            size += man.stat().st_size if man.exists() else 0
            d = by_dataset.setdefault(ds, {"bytes": 0, "files": 0, "rows": 0})
            d["bytes"] += size
            d["files"] += 1
            total += size
        for ds, d in by_dataset.items():
            d["rows"] = self._rows.get(ds, 0)
            d["bytes_per_row"] = round(d["bytes"] / max(d["rows"], 1), 2)
        return {
            "total_bytes": total,
            "total_mb": round(total / 1024**2, 2),
            "by_dataset": by_dataset,
        }


def interval_mean_held(series: np.ndarray, step: int) -> np.ndarray:
    """Block means of a 1-minute series, held across each block.

    The returned array is the same length as the input, with every minute of a
    block carrying that block's mean.  That is what lets the 30-minute meter
    era reuse :func:`~baile_nua.observation.sensors.observe_channel` unchanged:
    the function samples a 1-minute truth at the device's interval, so holding
    the mean means whichever minute it samples carries the interval's average
    power rather than an instant of it.

    A module-level function, not a block inside ``add_day``, so that the
    equality "the published half-hour value is the mean of its thirty minutes"
    can be tested without a simulated run behind it.
    """
    a = np.asarray(series, dtype=np.float64)
    if step <= 0:
        raise ValueError(f"step must be positive, got {step}")
    if len(a) % step:
        raise ValueError(
            f"series of {len(a)} does not divide into {step}-minute intervals; "
            f"a part-interval would publish a mean over fewer minutes than the "
            f"interval it is stamped with"
        )
    return np.repeat(a.reshape(len(a) // step, step).mean(axis=1), step)


def _epoch_mean(series: np.ndarray, step: int) -> np.ndarray:
    """Mean over each epoch.  Length must divide the day exactly."""
    a = np.asarray(series, dtype=np.float64)
    if len(a) % step:
        raise ValueError(f"series of {len(a)} does not divide into {step}-minute epochs")
    return a.reshape(len(a) // step, step).mean(axis=1)


def _unit(channel: str) -> str:
    from baile_nua.observation.sensors import DEVICE_SPECS

    return DEVICE_SPECS[channel].unit
