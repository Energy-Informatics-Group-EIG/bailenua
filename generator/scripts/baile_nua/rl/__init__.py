"""RL interface schema stub (design 9.3 day 1, design 7.6).

E1 delivers the **schema and its information boundary**, not a trained agent and
not an environment implementation.  The design is explicit that the Gymnasium
environment is hosted by BNIT (7.6) and that WP9 sim-to-real has no date (9.5).

What is in scope for E1 is the part that must be right before anything trains
against it: the five-interface boundary from design 7.6, declared as data so the
interface audit can be automated rather than reviewed by eye.
"""

from baile_nua.rl.interface import (
    RL_INTERFACE,
    Interface,
    InterfaceAuditError,
    audit_observation_space,
    observation_fields_for_tier,
)

__all__ = [
    "RL_INTERFACE",
    "Interface",
    "InterfaceAuditError",
    "audit_observation_space",
    "observation_fields_for_tier",
]
