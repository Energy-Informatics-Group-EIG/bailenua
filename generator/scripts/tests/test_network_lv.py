"""S11: the LV network, held to the physics rather than to its own output.

A power-flow model is easy to test badly. "It converged" says nothing — a
network with the wrong impedances converges. "Loading is under 100%" says
nothing either, because a model that lost half its load would also pass it. So
these tests check the things that are true of a real radial LV network and
would be false of a plausible-looking mistake:

* **conservation.** Power measured at the transformers must equal the sum of
  the customer loads plus losses, and the losses must be a small positive
  fraction. A sign error, a dropped connection or a mis-scaled unit all break
  this and nothing else would catch them.
* **sign, both ways.** Import positive and export negative at *every* element
  kind. The first version of ``d17_rows`` emitted -50.8 kW for a substation
  serving 21 importing homes, because pandapower measures ``p_lv_mw`` into the
  LV terminal, and the module's own docstring said the opposite two hundred
  lines above.
* **monotonicity.** Doubling every load must raise every loading and lower
  every voltage. A model whose answer does not move with its input is not
  solving anything.
* **radiality.** Irish LV is radial. A built network with a loop in it would
  give voltages a real circuit does not have.
* **the refusal holds.** ``assert_voltage_is_not_a_claim`` must raise, and the
  loading report must say in words that voltage is not the claim.
"""

from __future__ import annotations

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.network import lv
from baile_nua.population.synthesise import synthesise_t0

SEED = 20251010


@pytest.fixture(scope="module")
def town_net():
    town = synthesise_t0(master_seed=SEED)
    blds = {b.building_id: b for b in town.buildings}
    return lv.build_town_network(buildings=blds), blds


def _flat(tn, w: float) -> dict[str, float]:
    return {bid: float(w) for bid in tn.load_by_building}


# --------------------------------------------------------------------------- #
# the network itself
# --------------------------------------------------------------------------- #

def test_every_dwelling_in_the_town_has_exactly_one_connection(town_net):
    """A dwelling without a connection understates every loading above it."""
    tn, blds = town_net
    assert set(tn.load_by_building) == set(blds), (
        "the network's connections and the town's dwellings differ; a power "
        "flow that omits a connection understates every loading upstream"
    )
    assert len(tn.net.load) == len(blds)
    assert len(set(tn.net.load.bus)) == len(blds), (
        "two dwellings share a connection bus, so their service drops are "
        "not independent"
    )


def test_the_network_is_radial(town_net):
    """Irish LV is radial: buses = branches + 1 per galvanic island.

    A loop would give voltages a real circuit does not have, and would do it
    quietly - the flow still converges.
    """
    import networkx as nx

    import pandapower.topology as top

    tn, _ = town_net
    g = top.create_nxgraph(tn.net, respect_switches=True)
    assert nx.is_forest(g), (
        "the LV network contains a cycle. Irish LV distribution is operated "
        "radially, and a meshed model gives different voltages for reasons "
        "that are not in the town."
    )


def test_transformers_are_sized_from_the_catalogue_not_declared(town_net):
    """Every transformer and cable must be a published standard type."""
    tn, _ = town_net
    std_trafo = {name for _, name in lv.STD_TRAFO}
    assert set(tn.net.trafo.std_type) <= std_trafo
    assert set(tn.net.line.std_type) <= set(lv.STD_CABLE.values())
    # And the catalogue, not this test, is where the numbers live.
    for t in set(tn.net.trafo.std_type):
        assert t in tn.net.std_types["trafo"], (
            f"{t} is not in pandapower's standard-type catalogue, so its "
            f"impedance came from somewhere this build wrote"
        )


# --------------------------------------------------------------------------- #
# the physics
# --------------------------------------------------------------------------- #

def test_power_is_conserved_through_the_transformers(town_net):
    """Transformer power = customer load + losses, and losses are small.

    The single most informative check here. A sign error, a dropped
    connection, a unit mis-scale by 1000 and a double-counted load all break
    conservation and would break nothing else in this file.
    """
    tn, _ = town_net
    load = _flat(tn, 2000.0)
    lv.solve_epoch(tn, net_w_by_building=load)
    rows = lv.d17_rows(tn, ts="T", coupling_mode="C2", epoch_staleness_s=0)
    at_trafo = sum(r["p_kw"] for r in rows if r["element_kind"] == "transformer")
    at_homes = sum(load.values()) / 1000.0

    assert at_trafo > at_homes, (
        f"the transformers delivered {at_trafo:.1f} kW to serve {at_homes:.1f} "
        f"kW of load. Power into an LV network must EXCEED the load, by its "
        f"losses; a shortfall means load has been lost or a sign is wrong."
    )
    losses_pct = 100.0 * (at_trafo - at_homes) / at_homes
    assert 0.05 < losses_pct < 5.0, (
        f"LV losses came out at {losses_pct:.3f}% of load. Below 0.05% the "
        f"impedances are not doing anything; above 5% they are implausible "
        f"for a radial LV network at this loading, and either way the "
        f"conservation is being met by the wrong arithmetic."
    )


def test_import_is_positive_and_export_is_negative_at_every_element(town_net):
    """D17's sign convention, in both directions and at both element kinds.

    This is the test the first version of `d17_rows` failed: pandapower
    measures `p_lv_mw` INTO the LV terminal, so power delivered out to the
    customers reads negative there, and the rows contradicted the module's own
    stated convention.
    """
    tn, _ = town_net

    lv.solve_epoch(tn, net_w_by_building=_flat(tn, 2000.0))
    importing = lv.d17_rows(tn, ts="T", coupling_mode="C2", epoch_staleness_s=0)
    for kind in ("transformer", "feeder"):
        vals = [r["p_kw"] for r in importing if r["element_kind"] == kind]
        assert vals and all(v > 0 for v in vals), (
            f"every dwelling is importing 2 kW and some {kind} reports "
            f"negative p_kw: {[v for v in vals if v <= 0][:3]}"
        )

    lv.solve_epoch(tn, net_w_by_building=_flat(tn, -3000.0))
    exporting = lv.d17_rows(tn, ts="T", coupling_mode="C2", epoch_staleness_s=0)
    for kind in ("transformer", "feeder"):
        vals = [r["p_kw"] for r in exporting if r["element_kind"] == kind]
        assert vals and all(v < 0 for v in vals), (
            f"every dwelling is exporting 3 kW and some {kind} reports "
            f"positive p_kw: {[v for v in vals if v >= 0][:3]}"
        )


def test_loading_rises_and_voltage_falls_when_load_doubles(town_net):
    """A model whose answer does not move with its input is not solving."""
    tn, _ = town_net
    a = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 1500.0))
    b = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 3000.0))

    assert b["max_trafo_loading_pct"] > a["max_trafo_loading_pct"]
    assert b["max_line_loading_pct"] > a["max_line_loading_pct"]
    assert b["vm_pu_min"] < a["vm_pu_min"], (
        "doubling every load did not lower the worst voltage, so the cable "
        "impedances are not in the answer"
    )
    # Loading is linear in power to within the losses, so doubling the load
    # must roughly double the loading. A factor far from 2 means something
    # else is setting it.
    ratio = b["max_trafo_loading_pct"] / a["max_trafo_loading_pct"]
    assert 1.9 < ratio < 2.15, (
        f"doubling the load changed transformer loading by {ratio:.3f}x, not "
        f"about 2x. Loading is apparent power over a fixed rating, so it is "
        f"linear in power up to the losses."
    )


def test_exporting_raises_the_voltage(town_net):
    """Voltage RISE on export is the mechanism that constrains Irish PV.

    Checked because it is physics the model must get right even though the
    voltage number itself may not be claimed (A-49).
    """
    tn, _ = town_net
    imp = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 2000.0))
    exp = lv.solve_epoch(tn, net_w_by_building=_flat(tn, -3000.0))
    assert exp["vm_pu_max"] > 1.0, (
        f"every dwelling is exporting and the highest voltage is "
        f"{exp['vm_pu_max']}, at or below nominal. Reverse power flow through "
        f"a series impedance raises the voltage; this is the constraint that "
        f"limits PV on a real LV feeder."
    )
    assert exp["vm_pu_max"] > imp["vm_pu_max"]


def test_a_connection_with_no_place_in_the_network_is_an_error(town_net):
    tn, _ = town_net
    bad = dict(_flat(tn, 1000.0))
    bad["B-NOT-IN-THE-TOWN"] = 5000.0
    with pytest.raises(lv.NetworkError, match="no connection in"):
        lv.solve_epoch(tn, net_w_by_building=bad)


def test_a_building_with_no_estate_cannot_be_connected():
    """S11 takes topology from S02; it does not invent a substation."""
    class Stray:
        building_id = "B-STRAY"
        estate_id = None

    with pytest.raises(lv.NetworkError, match="no estate_id"):
        lv.build_town_network(buildings={"hh": Stray()})


# --------------------------------------------------------------------------- #
# the week-3 criterion, and the refusal that bounds it
# --------------------------------------------------------------------------- #

def test_the_loading_report_answers_the_week_3_criterion(town_net):
    """design 9.4 week 3: "feeder loading within physical limits"."""
    tn, _ = town_net
    results = [lv.solve_epoch(tn, net_w_by_building=_flat(tn, w))
               for w in (500.0, 1500.0, 2500.0)]
    rep = lv.loading_report(results)
    assert rep["measured"] is True
    assert rep["n_epochs"] == 3
    assert rep["limit_pct"] == 100.0
    assert rep["within_physical_limits"] is True
    assert "definition of the rating" in rep["limit_is_not_declared"], (
        "the report must say that 100% is a rating and not a threshold this "
        "build chose, or a reader cannot tell it from a declared band"
    )
    assert "Loading is the claim" in rep["voltage_is_reported_not_claimed"]


def test_an_overloaded_network_is_reported_as_overloaded(town_net):
    """The criterion has to be able to FAIL, or passing it means nothing."""
    tn, _ = town_net
    # 25 kW per dwelling: beyond any domestic connection, and chosen to be
    # unambiguously over a 400 kVA substation's rating while still SOLVING.
    # 40 kW was tried first and the flow would not converge, which is a
    # different result and is tested separately below - a criterion has to be
    # able to fail by being over the limit, not only by collapsing.
    r = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 25_000.0))
    assert r["converged"] is True
    rep = lv.loading_report([r])
    assert rep["within_physical_limits"] is False, (
        "every dwelling is drawing 25 kW and the report says the network is "
        "within physical limits. A criterion that cannot fail is not a check."
    )
    assert rep["n_epochs_with_a_transformer_over_limit"] == 1
    assert rep["max_transformer_loading_pct"] > 100.0


def test_a_network_too_stressed_to_solve_fails_the_criterion(town_net):
    """Non-convergence is a result, not a missing measurement.

    A radial LV network whose power flow will not converge is one that cannot
    supply the load. Reporting that as "not measured" would let the worst hour
    of a year decide nothing, and a ten-year town run cannot abort on it
    either - so it is recorded and counted against the criterion.
    """
    tn, _ = town_net
    r = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 40_000.0),
                       on_nonconvergence="record")
    assert r["converged"] is False
    assert r["max_trafo_loading_pct"] is None, (
        "a non-converged epoch reported a loading. There is no solution to "
        "read one from, and emitting the last successful solve's numbers "
        "under this epoch's timestamp is how a non-convergence goes unnoticed."
    )
    rep = lv.loading_report([r])
    assert rep["within_physical_limits"] is False
    assert rep["n_epochs_that_did_not_converge"] == 1

    # And it must not be averaged away by the epochs that did solve.
    good = lv.solve_epoch(tn, net_w_by_building=_flat(tn, 1500.0))
    mixed = lv.loading_report([good, r])
    assert mixed["within_physical_limits"] is False, (
        "one non-converging epoch among many was averaged away. The "
        "criterion is about the worst hour, not the mean one."
    )
    assert mixed["n_epochs_solved"] == 1
    assert mixed["n_epochs_that_did_not_converge"] == 1


def test_the_default_is_to_raise_on_non_convergence(town_net):
    """A single epoch being examined must not come back quietly broken."""
    tn, _ = town_net
    with pytest.raises(lv.NetworkError, match="did not converge"):
        lv.solve_epoch(tn, net_w_by_building=_flat(tn, 40_000.0))


def test_voltage_may_not_be_turned_into_a_claim():
    with pytest.raises(lv.VoltageClaimError, match="A-49"):
        lv.assert_voltage_is_not_a_claim()


def test_the_declared_topology_names_what_each_quantity_affects():
    """A-49. Every declared quantity must say what it does to the answer.

    Without that, a reader cannot tell which results survive the flag - and
    the whole argument for reporting loading while withholding voltage rests
    on exactly this distinction.
    """
    for name, spec in lv.TOPOLOGY_A_FLAGS.items():
        assert "value" in spec and "why" in spec and "affects" in spec, name
        assert spec["why"].strip(), name
        assert spec["affects"].strip(), name
    # And the two load-bearing claims about insensitivity must be stated.
    assert "not at all" in lv.TOPOLOGY_A_FLAGS["feeder_span_m"]["affects"], (
        "the feeder span must state that it does NOT affect loading, because "
        "that is why loading may be claimed while voltage may not"
    )
    assert "not at all" in (
        lv.TOPOLOGY_A_FLAGS["connections_per_feeder"]["affects"])


def test_the_voltage_limits_are_the_standards_not_a_choice():
    """EN 50160 / ESB Distribution Code: 230 V +/-10%."""
    assert lv.VOLTAGE_LIMITS_PU == (0.90, 1.10)
    assert "EN 50160" in lv.VOLTAGE_STANDARD
    assert lv.NOMINAL_LV_KV == 0.4
    assert lv.NOMINAL_MV_KV == 20.0


def test_d17_rows_conform_to_the_published_schema(town_net):
    """The rows must satisfy D17 as datasets.yaml defines it, not as this
    module imagines it."""
    import yaml
    from pathlib import Path

    tn, _ = town_net
    lv.solve_epoch(tn, net_w_by_building=_flat(tn, 2000.0))
    rows = lv.d17_rows(tn, ts="2022-01-15T18:00:00+00:00",
                       coupling_mode="C2", epoch_staleness_s=0)
    spec = yaml.safe_load(
        (Path(lv.__file__).resolve().parents[1] / "schema" / "datasets.yaml")
        .read_text(encoding="utf-8"))
    ds = spec["datasets"] if "datasets" in spec else spec
    fields = {f["name"]: f for f in ds["D17"]["fields"]}
    required = {n for n, f in fields.items() if f.get("required")}

    assert rows, "no D17 rows were produced"
    for r in rows:
        assert required <= set(r), (
            f"a D17 row is missing required fields "
            f"{sorted(required - set(r))}"
        )
        assert not (set(r) - set(fields)), (
            f"a D17 row carries fields D17 does not define: "
            f"{sorted(set(r) - set(fields))}"
        )
        assert isinstance(r["outage"], bool)
        assert r["coupling_mode"] in ("C1", "C2")
        assert np.isfinite(r["p_kw"]) and np.isfinite(r["loading_pct"])
