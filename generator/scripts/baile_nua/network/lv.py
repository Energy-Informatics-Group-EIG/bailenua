"""S11: the town's LV network, and the first solved power flow in the build.

``NETWORK_CLAIM`` has said since E1 that **no** voltage, loading, curtailment or
network-constraint claim may be made, because the epoch barrier aggregates net
load onto a feeder and does not solve anything. Design 9.3 moves pandapower to
week 3 and design 9.4's week-3 acceptance criterion is "**feeder loading within
physical limits**" — which is a claim about a solved power flow, so it cannot be
made until there is one. This module is that power flow.

**What is sourced, and what is not.** The split matters more here than almost
anywhere else in the build, because a network model has two very different
kinds of input:

===========================  ==================================================
*electrical parameters*      **sourced.** Cable resistance, reactance and
                             thermal rating, and transformer rated power,
                             short-circuit and no-load losses, come from
                             pandapower's standard-type catalogue — published
                             European standard types (NAYY 4x150 SE, NAYY
                             4x120 SE, 0.4 and 0.63 MVA 20/0.4 kV). Not one
                             impedance is written here.
*voltage limits*             **sourced.** EN 50160 and the ESB Networks
                             Distribution Code: 230 V nominal, +/-10%, so
                             0.90 to 1.10 per unit.
*voltage level*              **sourced.** Irish distribution is 20 kV MV and
                             400/230 V LV.
*topology*                   ``[A]``, registered as A-49. ESB Networks does not
                             publish Cobh's actual LV network — which circuits
                             exist, which house is on which, how long each
                             cable run is. The shape here is derived from the
                             town's own 53 estates and declared, and every
                             declared quantity is in :data:`TOPOLOGY_A_FLAGS`
                             with its effect on the answer stated.
===========================  ==================================================

**Why the topology being ``[A]`` does not make the result worthless, and what
it does restrict.** Loading on a transformer is the sum of its customers' net
power divided by its rating, and that is almost insensitive to how the cables
are arranged: a 400 kVA substation serving 40 homes is at the same loading
whether they are on one circuit or four. **Transformer loading is therefore
robust to the ``[A]``.** Voltage drop is the opposite — it is a line integral
along the actual circuit, so a declared cable length puts a declared number
straight into the volts. So:

* transformer and feeder **loading** may be reported, and is;
* **voltage** is computed, recorded in D17 because the schema has the field, and
  **must not be used to support a claim** until the topology is sourced.
  :func:`assert_voltage_is_not_a_claim` exists to make that refusal executable
  rather than a sentence in a docstring.

**Quasi-static, which is what S11 says.** One power flow per epoch, with the
epoch's net power as a constant load. No dynamics, no protection, no transient
stability. The design's S11 row says "1 min (quasi-static power flow)" and this
solves at whatever epoch it is handed, recording ``epoch_staleness_s`` so a
reader of D17 knows how old the load was when the flow was solved.

**Sign convention.** pandapower's ``p_mw`` on a load is positive for
consumption. A home exporting PV is a negative load, not a generator, which
keeps one element per connection and one sign convention through the whole
model: D17's ``p_kw`` is positive for import at every element.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np

__all__ = [
    "NOMINAL_LV_KV",
    "NOMINAL_MV_KV",
    "VOLTAGE_LIMITS_PU",
    "VOLTAGE_STANDARD",
    "STD_TRAFO",
    "STD_CABLE",
    "TOPOLOGY_A_FLAGS",
    "LOADING_LIMIT_PCT",
    "NetworkError",
    "VoltageClaimError",
    "TownNetwork",
    "build_town_network",
    "solve_epoch",
    "d17_rows",
    "assert_voltage_is_not_a_claim",
    "loading_report",
]

#: Irish LV, phase-to-phase. 230 V phase-to-neutral is 400/sqrt(3).
NOMINAL_LV_KV = 0.4

#: Irish MV distribution.
NOMINAL_MV_KV = 20.0

#: EN 50160 / ESB Networks Distribution Code: 230 V nominal, +/-10%.
VOLTAGE_LIMITS_PU: tuple[float, float] = (0.90, 1.10)

VOLTAGE_STANDARD = (
    "EN 50160 and the ESB Networks Distribution Code: LV supply voltage "
    "230 V nominal +/-10%, so 0.90 to 1.10 per unit. A standard, not a "
    "statistic - it is a published requirement on the network operator."
)

#: An element at or above its rating is at its physical limit. Not a declared
#: threshold: 100% of a thermal rating is the definition of the rating.
LOADING_LIMIT_PCT = 100.0

#: pandapower standard types, by number of connections the substation serves.
#: The two sizes are the ones Irish ground-mounted distribution substations
#: actually come in; which of the two a given substation is, is part of A-49.
STD_TRAFO: tuple[tuple[int, str], ...] = (
    (28, "0.4 MVA 20/0.4 kV"),
    (10_000, "0.63 MVA 20/0.4 kV"),
)

#: LV feeder cable, and the spur to each house. Standard types, so the
#: impedances are catalogue values rather than numbers written here.
STD_CABLE = {"feeder": "NAYY 4x150 SE", "service": "NAYY 4x50 SE"}

#: ``[A]``, registered as A-49. Every declared quantity in the topology, with
#: what it does to the answer - so a reader can see which results survive it.
TOPOLOGY_A_FLAGS: dict[str, dict[str, Any]] = {
    "connections_per_feeder": {
        "value": 24,
        "why": (
            "ESB Networks does not publish which houses share an LV circuit. "
            "24 is declared at the middle of the range an LV feeder serves."
        ),
        "affects": "voltage drop strongly; transformer loading not at all",
    },
    "feeder_span_m": {
        "value": 300.0,
        "why": (
            "the length of an LV circuit from the substation to its last "
            "connection. Declared; Cobh's actual cable routes are not public."
        ),
        "affects": "voltage drop directly and linearly; loading not at all",
    },
    "service_drop_m": {
        "value": 15.0,
        "why": "the spur from the feeder to one house. Declared.",
        "affects": "that house's voltage only",
    },
    "power_factor": {
        "value": 0.98,
        "why": (
            "domestic load is close to unity and slightly inductive. The model "
            "computes real power only, so the reactive part is declared rather "
            "than simulated - S10 renders no reactive power."
        ),
        "affects": (
            "apparent power, hence loading, by 1/0.98 = 1.02x; and voltage "
            "drop through the reactive term"
        ),
    },
}


class NetworkError(RuntimeError):
    pass


class VoltageClaimError(RuntimeError):
    """Raised when a computed voltage is reached for as evidence."""


def assert_voltage_is_not_a_claim() -> None:
    """Always raises. Voltages are recorded; they do not support a claim.

    Loading is a ratio of powers and survives the declared topology. Voltage is
    a line integral along a circuit this module declares rather than knows, so
    a voltage result is a property of A-49 as much as of the town. Executable
    so that using it means deleting a line that says not to.
    """
    raise VoltageClaimError(
        "Voltage per unit is computed and written to D17 because the schema "
        "has the field, and it must NOT be used to support a claim while the "
        "LV topology is [A] (A-49): the number of connections per feeder, the "
        "feeder span and the service-drop length are declared, and voltage "
        "drop is a line integral along exactly those. Transformer and feeder "
        "LOADING is what this module supports, because it is a ratio of powers "
        "and is insensitive to how the connections are arranged. To make a "
        "voltage claim, source the topology first."
    )


@dataclasses.dataclass
class TownNetwork:
    """The built network, plus the maps a solver needs to load it."""

    net: Any
    #: building_id -> pandapower load index.
    load_by_building: dict[str, int]
    #: substation id -> pandapower trafo index.
    trafo_by_substation: dict[str, int]
    #: feeder id -> the line index at its head, where its loading is read.
    head_line_by_feeder: dict[str, int]
    #: building_id -> (substation, feeder)
    assignment: dict[str, tuple[str, str]]
    diagnostics: dict[str, Any]


def _trafo_type(n_connections: int) -> str:
    for cap, name in STD_TRAFO:
        if n_connections <= cap:
            return name
    raise NetworkError(f"no transformer type for {n_connections} connections")


def build_town_network(
    *, buildings: Any, estate_of: Any = None,
) -> TownNetwork:
    """A radial LV network for the town, from its own estates.

    ``buildings`` maps any key to an object carrying ``building_id`` and
    ``estate_id`` — the slice's ``sl.buildings`` or the town's, so the same
    function serves a 60-home slice and the full 1,092-home town.

    One substation per estate, its transformer sized from the number of
    connections; connections split into feeders of at most
    ``connections_per_feeder``; each feeder a chain of cable sections with a
    house spurred off each node. Radial, which is what Irish LV is.
    """
    import pandapower as pp

    per_feeder = int(TOPOLOGY_A_FLAGS["connections_per_feeder"]["value"])
    span_m = float(TOPOLOGY_A_FLAGS["feeder_span_m"]["value"])
    drop_m = float(TOPOLOGY_A_FLAGS["service_drop_m"]["value"])

    items = []
    for key, b in buildings.items() if hasattr(buildings, "items") else enumerate(buildings):
        bid = getattr(b, "building_id", None)
        if bid is None:
            raise NetworkError(f"{key!r} has no building_id, so it cannot be connected")
        est = (estate_of(b) if callable(estate_of)
               else getattr(b, "estate_id", None))
        if est is None:
            raise NetworkError(
                f"{bid} has no estate_id, so there is nothing to derive its "
                f"substation from. S11 takes topology from S02; inventing a "
                f"substation per house would make the loading meaningless."
            )
        items.append((str(est), str(bid)))
    if not items:
        raise NetworkError("no buildings to connect")

    by_estate: dict[str, list[str]] = {}
    for est, bid in sorted(items):
        by_estate.setdefault(est, []).append(bid)

    net = pp.create_empty_network(name="Baile Nua LV", sn_mva=1.0)
    mv = pp.create_bus(net, vn_kv=NOMINAL_MV_KV, name="MV-SOURCE")
    # The MV side is a slack bus: this models the LV network, not the MV one,
    # and pretending to know the MV source impedance would be a declared
    # number doing work in a result.
    pp.create_ext_grid(net, mv, vm_pu=1.0, name="MV grid")

    load_by_building: dict[str, int] = {}
    trafo_by_sub: dict[str, int] = {}
    head_line: dict[str, int] = {}
    assignment: dict[str, tuple[str, str]] = {}

    for est in sorted(by_estate):
        bids = by_estate[est]
        sub = f"SUB-{est}"
        lv_bus = pp.create_bus(net, vn_kv=NOMINAL_LV_KV, name=f"{sub}-LV")
        trafo_by_sub[sub] = pp.create_transformer(
            net, mv, lv_bus, std_type=_trafo_type(len(bids)), name=sub)

        n_feeders = max(1, math.ceil(len(bids) / per_feeder))
        chunks = [bids[i::n_feeders] for i in range(n_feeders)]
        for fi, chunk in enumerate(chunks):
            if not chunk:
                continue
            feeder = f"FDR-{est}-{fi:02d}"
            # The span is divided among the connections on the circuit, so a
            # feeder with fewer houses has shorter sections rather than the
            # same length per house. That is what a real circuit does: the
            # span is the distance to the end of the street.
            section_km = (span_m / max(len(chunk), 1)) / 1000.0
            upstream = lv_bus
            for ci, bid in enumerate(chunk):
                node = pp.create_bus(net, vn_kv=NOMINAL_LV_KV,
                                     name=f"{feeder}-N{ci:02d}")
                li = pp.create_line(
                    net, upstream, node, length_km=section_km,
                    std_type=STD_CABLE["feeder"], name=f"{feeder}-S{ci:02d}")
                if ci == 0:
                    head_line[feeder] = li
                svc = pp.create_bus(net, vn_kv=NOMINAL_LV_KV, name=f"CONN-{bid}")
                pp.create_line(
                    net, node, svc, length_km=drop_m / 1000.0,
                    std_type=STD_CABLE["service"], name=f"SVC-{bid}")
                load_by_building[bid] = pp.create_load(
                    net, svc, p_mw=0.0, q_mvar=0.0, name=bid)
                assignment[bid] = (sub, feeder)
                upstream = node

    diagnostics = {
        "design_ref": "S11; design 9.3 (pandapower in week 3); 9.4 week-3 acceptance",
        "n_connections": len(load_by_building),
        "n_substations": len(trafo_by_sub),
        "n_feeders": len(head_line),
        "n_buses": int(len(net.bus)),
        "n_lines": int(len(net.line)),
        "trafo_sizes": {
            sub: str(net.trafo.at[ti, "std_type"])
            for sub, ti in sorted(trafo_by_sub.items())
        },
        "electrical_parameters_are_sourced": (
            "pandapower standard types: cables "
            f"{STD_CABLE} and transformers {[n for _, n in STD_TRAFO]}. "
            "Published European standard types; no impedance is written in "
            "this module."
        ),
        "voltage_standard": VOLTAGE_STANDARD,
        "topology_is_a_flagged": "A-49",
        "topology_a_flags": TOPOLOGY_A_FLAGS,
        "what_may_be_claimed": (
            "Transformer and feeder LOADING. It is a ratio of powers and is "
            "insensitive to how connections are arranged on a circuit."
        ),
        "what_may_not": (
            "VOLTAGE. It is a line integral along a declared topology, so it "
            "is a property of A-49 as much as of the town. Recorded in D17, "
            "and assert_voltage_is_not_a_claim() raises."
        ),
    }
    return TownNetwork(net=net, load_by_building=load_by_building,
                       trafo_by_substation=trafo_by_sub,
                       head_line_by_feeder=head_line, assignment=assignment,
                       diagnostics=diagnostics)


def solve_epoch(
    tn: TownNetwork, *, net_w_by_building: dict[str, float],
    power_factor: float | None = None,
    on_nonconvergence: str = "raise",
) -> dict[str, Any]:
    """One quasi-static power flow for one epoch's net power.

    A building the network does not have is an error rather than a skip: a
    power flow that silently omits a connection understates every loading
    upstream of it, which is precisely the number this exists to produce.

    ``on_nonconvergence`` decides what a network too stressed to solve means.
    Both options exist because the answer differs by caller and neither is a
    fallback:

    ``"raise"`` (default)
        for a single epoch being examined. A non-converging flow is reported,
        never replaced with the previous epoch's answer.

    ``"record"``
        for a long run. Newton-Raphson failing to converge on a radial LV
        network is not a missing measurement - it is the network being unable
        to supply the load, which is the strongest possible statement that it
        is NOT within physical limits. A ten-year town run must not abort on
        one such epoch and must not quietly skip it either, so the epoch comes
        back with ``converged: False`` and :func:`loading_report` counts it
        against the criterion.
    """
    import pandapower as pp

    pf = float(power_factor if power_factor is not None
               else TOPOLOGY_A_FLAGS["power_factor"]["value"])
    if not 0.0 < pf <= 1.0:
        raise NetworkError(f"power factor must be in (0, 1], got {pf}")
    tan_phi = math.sqrt(max(1.0 / (pf * pf) - 1.0, 0.0))

    unknown = sorted(set(net_w_by_building) - set(tn.load_by_building))
    if unknown:
        raise NetworkError(
            f"{len(unknown)} buildings have net power but no connection in "
            f"the network: {unknown[:5]}. A power flow that omits a connection "
            f"understates every loading upstream of it."
        )
    missing = sorted(set(tn.load_by_building) - set(net_w_by_building))

    net = tn.net
    for bid, li in tn.load_by_building.items():
        p_mw = float(net_w_by_building.get(bid, 0.0)) / 1e6
        net.load.at[li, "p_mw"] = p_mw
        # Reactive power follows the declared power factor and takes the sign
        # of the real power, so an exporting home does not import reactive.
        net.load.at[li, "q_mvar"] = p_mw * tan_phi

    if on_nonconvergence not in ("raise", "record"):
        raise NetworkError(
            f"on_nonconvergence must be 'raise' or 'record', got "
            f"{on_nonconvergence!r}"
        )
    failure: str | None = None
    try:
        pp.runpp(net, numba=False)
        if not bool(net.converged):
            failure = "pandapower reported the flow as not converged"
    except Exception as exc:                        # noqa: BLE001
        failure = f"{type(exc).__name__}: {exc}"
    if failure is not None:
        if on_nonconvergence == "raise":
            raise NetworkError(
                f"the power flow did not converge: {failure}. A "
                f"non-converging flow is reported, never replaced with the "
                f"previous epoch's answer."
            )
        total_kw = sum(net_w_by_building.values()) / 1000.0
        return {
            "converged": False,
            "why": failure,
            "n_connections_loaded": len(net_w_by_building),
            "total_load_kw": round(total_kw, 3),
            "power_factor": pf,
            "reading": (
                "The network could not be solved at this epoch's load. That "
                "is not a missing measurement: a radial LV network whose "
                "power flow will not converge is one that cannot supply the "
                "load, which is the strongest statement available that it is "
                "NOT within physical limits. loading_report counts this "
                "epoch against the criterion rather than dropping it."
            ),
            # No loading or voltage figures: there is no solution to read them
            # from, and emitting the last successful solve's numbers under
            # this epoch's timestamp is how a non-convergence becomes
            # invisible.
            "trafo_loading_pct": {},
            "feeder_head_loading_pct": {},
            "max_trafo_loading_pct": None,
            "max_feeder_loading_pct": None,
            "max_line_loading_pct": None,
            "vm_pu_min": None,
            "vm_pu_max": None,
            "n_buses_outside_en50160": None,
        }

    vm = net.res_bus.vm_pu.to_numpy(dtype=np.float64)
    lo, hi = VOLTAGE_LIMITS_PU
    trafo_loading = {
        sub: float(net.res_trafo.at[ti, "loading_percent"])
        for sub, ti in tn.trafo_by_substation.items()
    }
    feeder_loading = {
        f: float(net.res_line.at[li, "loading_percent"])
        for f, li in tn.head_line_by_feeder.items()
    }
    return {
        "converged": True,
        "n_connections_loaded": len(net_w_by_building),
        "n_connections_at_zero": len(missing),
        "power_factor": pf,
        "trafo_loading_pct": trafo_loading,
        "feeder_head_loading_pct": feeder_loading,
        "max_trafo_loading_pct": max(trafo_loading.values(), default=0.0),
        "max_feeder_loading_pct": max(feeder_loading.values(), default=0.0),
        "max_line_loading_pct": float(net.res_line.loading_percent.max()),
        "vm_pu_min": float(vm.min()),
        "vm_pu_max": float(vm.max()),
        "n_buses_outside_en50160": int(((vm < lo) | (vm > hi)).sum()),
        "voltage_is_not_a_claim": (
            "recorded because D17 has the field; see "
            "assert_voltage_is_not_a_claim() and A-49"
        ),
    }


def d17_rows(
    tn: TownNetwork, *, ts: Any, coupling_mode: str, epoch_staleness_s: int,
) -> list[dict[str, Any]]:
    """The solved state as D17 rows, after :func:`solve_epoch`.

    ``outage`` is False throughout: S11 lists outages as an output and nothing
    in the model opens a switch yet, so the field is populated honestly rather
    than left for a reader to interpret.
    """
    net = tn.net
    rows: list[dict[str, Any]] = []
    for sub, ti in sorted(tn.trafo_by_substation.items()):
        rows.append({
            "ts": ts, "element_id": sub, "element_kind": "transformer",
            # NEGATED. pandapower measures p_lv_mw flowing INTO the LV
            # terminal, so power delivered out to the customers is negative
            # there - and the first version of this emitted -50.8 kW for a
            # substation serving 21 importing homes, contradicting this
            # module's own stated convention two hundred lines above it. D17's
            # p_kw is positive for import at EVERY element kind, or the two
            # element kinds in one dataset cannot be summed or compared.
            "p_kw": -float(net.res_trafo.at[ti, "p_lv_mw"]) * 1000.0,
            "q_kvar": -float(net.res_trafo.at[ti, "q_lv_mvar"]) * 1000.0,
            "voltage_pu": float(
                net.res_bus.at[int(net.trafo.at[ti, "lv_bus"]), "vm_pu"]),
            "loading_pct": float(net.res_trafo.at[ti, "loading_percent"]),
            "outage": False, "coupling_mode": coupling_mode,
            "epoch_staleness_s": int(epoch_staleness_s),
        })
    for feeder, li in sorted(tn.head_line_by_feeder.items()):
        rows.append({
            "ts": ts, "element_id": feeder, "element_kind": "feeder",
            "p_kw": float(net.res_line.at[li, "p_from_mw"]) * 1000.0,
            "q_kvar": float(net.res_line.at[li, "q_from_mvar"]) * 1000.0,
            "voltage_pu": float(
                net.res_bus.at[int(net.line.at[li, "to_bus"]), "vm_pu"]),
            "loading_pct": float(net.res_line.at[li, "loading_percent"]),
            "outage": False, "coupling_mode": coupling_mode,
            "epoch_staleness_s": int(epoch_staleness_s),
        })
    return rows


def loading_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The week-3 criterion: is feeder loading within physical limits?

    Over however many epochs were solved. 100% is the definition of a thermal
    rating rather than a threshold this build chose, so there is nothing to
    declare and nothing to widen.
    """
    if not results:
        return {"measured": False, "why": "no epochs were solved"}
    # A non-converged epoch counts AGAINST the criterion and is not averaged
    # into the loadings, because it has none: taking the mean over only the
    # epochs that solved would report a comfortable figure for a network that
    # failed on its worst hour.
    failed = [r for r in results if not r.get("converged")]
    ok = [r for r in results if r.get("converged")]
    if not ok:
        return {
            "measured": True,
            "n_epochs": len(results),
            "n_epochs_that_did_not_converge": len(failed),
            "within_physical_limits": False,
            "why": (
                "no epoch converged, so the network could not supply any "
                "load it was given. There is no loading to report and the "
                "criterion fails."
            ),
        }
    tr = [r["max_trafo_loading_pct"] for r in ok]
    fd = [r["max_feeder_loading_pct"] for r in ok]
    ln = [r["max_line_loading_pct"] for r in ok]
    vmin = [r["vm_pu_min"] for r in ok]
    n_over_t = sum(1 for v in tr if v > LOADING_LIMIT_PCT)
    n_over_f = sum(1 for v in ln if v > LOADING_LIMIT_PCT)
    return {
        "measured": True,
        "criterion": (
            "design 9.4 week 3: feeder loading within physical limits"
        ),
        "limit_pct": LOADING_LIMIT_PCT,
        "limit_is_not_declared": (
            "100% of an element's thermal rating is the definition of the "
            "rating, from pandapower's standard-type catalogue. There is no "
            "threshold here that this build chose."
        ),
        "n_epochs": len(results),
        "max_transformer_loading_pct": round(max(tr), 3),
        "mean_of_epoch_max_transformer_loading_pct": round(
            float(np.mean(tr)), 3),
        "max_line_loading_pct": round(max(ln), 3),
        "max_feeder_head_loading_pct": round(max(fd), 3),
        "n_epochs_with_a_transformer_over_limit": n_over_t,
        "n_epochs_with_a_line_over_limit": n_over_f,
        "n_epochs_that_did_not_converge": len(failed),
        "n_epochs_solved": len(ok),
        "within_physical_limits": bool(
            n_over_t == 0 and n_over_f == 0 and not failed),
        "non_convergence_counts_against_the_criterion": (
            "A network whose power flow will not converge cannot supply the "
            "load. Reporting it as 'not measured' would let the worst hour of "
            "a year decide nothing."
        ),
        "min_voltage_pu": round(min(vmin), 5),
        "voltage_is_reported_not_claimed": (
            "The minimum voltage is given so a reader can see it, and it "
            "supports nothing: the LV topology is [A] (A-49) and voltage drop "
            "is a line integral along exactly the declared quantities. "
            "Loading is the claim."
        ),
    }
