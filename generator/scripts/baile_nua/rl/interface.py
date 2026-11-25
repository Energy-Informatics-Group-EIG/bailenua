"""The RL information boundary, as data (design 7.6).

Design 7.6 gives a five-row table.  Reproduced here so that the two enforcement
mechanisms it names can be automated:

* the **interface audit** - "confirms that no reward components or diagnostics
  reach the agent";
* the **probe test** - trains a small model to predict GT occupancy or traits
  from the agent's internal state, and compares it against a probe trained on
  the same OBS history the agent received.  *The gap, not raw probe accuracy,
  measures privileged leakage* (review log 20).  E1 declares the contract; the
  probe itself needs a trained agent and is therefore WP9, not E1.

The observation space is derived from the schema's OBS datasets and the home's
sensor tier, so an agent cannot be handed a channel the home does not have.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Final

from baile_nua.schema import load
from baile_nua.schema.access import LeakageError, gt_field_names

__all__ = [
    "Interface",
    "RL_INTERFACE",
    "InterfaceAuditError",
    "audit_observation_space",
    "observation_fields_for_tier",
    "TIER_CHANNELS",
]


class InterfaceAuditError(LeakageError):
    """The agent interface would expose something design 7.6 forbids."""


@dataclasses.dataclass(frozen=True)
class Interface:
    name: str
    contents: str
    training: str
    inference: str
    notes: str = ""


#: Design 7.6, "RL information boundary", verbatim in structure.
RL_INTERFACE: Final[tuple[Interface, ...]] = (
    Interface(
        name="observations",
        contents="OBS at the home's sensor tier, tariff, weather forecast, grid signal, last clip/reject notice",
        training="allowed",
        inference="allowed",
    ),
    Interface(
        name="actions",
        contents="device setpoints, windows, rates, bids",
        training="allowed",
        inference="allowed",
    ),
    Interface(
        name="training_reward",
        contents="scalar only, computed from GT including latent comfort bands and lambda weights",
        training="allowed as a scalar, with no decomposition exposed",
        inference="not available",
        notes="Privileged information may be used in training ONLY through the scalar reward. "
              "An algorithm needing more (asymmetric actor-critic) must declare it and is "
              "reported separately.",
    ),
    Interface(
        name="evaluation_metrics",
        contents="cost, comfort minutes, violations, overrides, regret",
        training="never fed to the agent",
        inference="never",
    ),
    Interface(
        name="privileged_gt_scoring",
        contents="occupancy, traits, D20 labels",
        training="forbidden",
        inference="forbidden",
    ),
)

#: Channels available at each sensor tier (design 5.11, R10: tiers are drawn per
#: home, so detection difficulty varies across the town as it would in practice).
TIER_CHANNELS: Final[dict[str, tuple[str, ...]]] = {
    "T1": ("import_w", "export_w"),
    "T2": ("import_w", "export_w", "temp_living", "ct_circuit_a", "ct_circuit_b"),
    "T3": (
        "import_w", "export_w", "temp_living", "temp_sleep", "rh_living",
        "co2_living", "ct_circuit_a", "ct_circuit_b", "ct_ev", "ct_hp",
    ),
    "T4": (
        "import_w", "export_w", "temp_living", "temp_sleep", "temp_kitchen",
        "temp_bath", "rh_living", "rh_bath", "co2_living", "co2_sleep",
        "pir_hall", "pir_living", "ct_circuit_a", "ct_circuit_b", "ct_ev",
        "ct_hp", "ct_immersion", "ct_shower", "ct_wet_goods",
        "inverter_pv_w", "inverter_bess_w", "bess_soc_pct", "charger_w",
    ),
}

#: Exogenous series an agent may see alongside its own home's channels.
EXOGENOUS_OBSERVATIONS: Final[tuple[str, ...]] = (
    "tariff_import_eur_kwh",
    "tariff_export_eur_kwh",
    "weather_forecast_temp_c",
    "weather_forecast_ghi_w_m2",
    "grid_signal",
    "last_clip_notice",
    "last_reject_notice",
)


def observation_fields_for_tier(tier: str) -> tuple[str, ...]:
    """Legal observation keys for a home at ``tier``.

    Raises on an unknown tier rather than defaulting, because silently handing
    an agent the T1 set when T4 was meant would look like a working run.
    """
    try:
        channels = TIER_CHANNELS[tier]
    except KeyError:
        raise KeyError(f"unknown sensor tier {tier!r}; known: {sorted(TIER_CHANNELS)}") from None
    return channels + EXOGENOUS_OBSERVATIONS


def audit_observation_space(
    keys: Any, tier: str, *, include_reward_components: bool = False
) -> None:
    """The design 7.6 interface audit.

    Fails if the observation space contains a GT-class field name, a channel the
    home's tier does not have, or any reward decomposition.
    """
    keys = list(keys)
    legal = set(observation_fields_for_tier(tier))

    gt = gt_field_names(load())
    leaked = sorted(k for k in keys if k in gt)
    if leaked:
        raise InterfaceAuditError(
            f"RL observation space carries ground-truth fields {leaked}. "
            f"Design 7.6: privileged GT scoring (occupancy, traits, D20 labels) is "
            f"forbidden in training and inference."
        )

    reward_parts = sorted(
        k for k in keys
        if any(t in k.lower() for t in ("reward", "discomfort", "degree_minute", "lambda_", "penalty"))
    )
    if reward_parts and not include_reward_components:
        raise InterfaceAuditError(
            f"RL observation space carries reward components {reward_parts}. "
            f"Design 7.6: the training reward reaches the agent as a scalar only, "
            f"with no decomposition exposed."
        )

    off_tier = sorted(set(keys) - legal - set(reward_parts))
    if off_tier:
        raise InterfaceAuditError(
            f"RL observation space carries channels {off_tier} that a {tier} home "
            f"does not have. Design 7.6: observations are OBS at the home's own tier."
        )
