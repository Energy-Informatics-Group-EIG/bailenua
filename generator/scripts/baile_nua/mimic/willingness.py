"""The HRSD willingness model, generator G-B (design 5.14 independence protocol).

Design 5.14, binding:

    **Avoiding circularity.**  If HRSD answered with MIMIC's own ``chooseSignal``
    formula, MIMIC recovering it would prove only that the estimator works on
    its own assumptions.  HRSD's willingness model is therefore written
    independently.  It adds interactions, non-linearities, response styles,
    fatigue and the stated-revealed gap, so MIMIC is tested under realistic
    misspecification.

    **Specification firewall.**  G-B's functional form and parameters come from
    cited literature and are frozen in D24 *before* any MIMIC estimator is run
    on its output.  Any later change is logged in the review log with a reason.

:func:`specification` returns the frozen spec and :func:`specification_hash`
its content hash.  :func:`freeze_to_d24` writes both into the evidence view, and
the MIMIC runner refuses to start unless the hash on disk matches the code - so
the firewall is enforced rather than promised.

**How G-B differs from G-A structurally**, which is the whole point.  G-A
(``chooseSignal``) is an additive multinomial logit: a linear function of the
traits, with per-category additive terms, a constant shift for context *b*, and
satisficers handled by scaling the logits toward zero.  G-B differs in six ways,
each of which breaks a different assumption an estimator fitted to G-A would
make:

1. **Saturating utility.**  Traits enter through ``tanh``, so the effect of a
   trait flattens at the extremes instead of growing without limit.  A linear
   logit fitted to this will under-predict in the middle and over-predict in the
   tails.
2. **Trait interactions.**  Products such as ``env x conditional`` and
   ``community x instTrust`` carry real weight.  G-A has no trait-by-trait
   terms at all, so these are pure misspecification from its point of view.
3. **Multiplicative COM-B gating** (design 5.13).  Capability, Opportunity and
   Motivation multiply rather than add, so a person with zero opportunity does
   not act however motivated they are.  No additive model can represent that.
4. **Context enters multiplicatively.**  Grid stress and visibility *scale* the
   cooperative terms rather than shifting them by a constant, so the context
   effect depends on the person - which is exactly what an AMCE estimated as a
   constant (T7) will average over.
5. **Response styles and fatigue.**  Acquiescence and extreme-responding styles
   bias the choice independently of the traits, and both deliberation and
   cooperation decay with the item's position in the session and with how many
   flexibility asks the person has already seen (design 5.3 "fatigue after
   repeated flexibility asks").
6. **Stated vs revealed.**  The *stated* answer is shifted toward the socially
   desirable option by the person's ``stated_gap``; the *revealed* behaviour is
   not.  G-A has one quantity where G-B has two.

Position on screen is deliberately **not** an input, except in test mode T10
where a bias is planted on purpose (design 5.14: "never to screen position
(position bias is planted only in test mode T10)").
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Literal

import numpy as np

from baile_nua.hashing import hash_json

__all__ = [
    "SIGNALS",
    "CATEGORIES",
    "GBSpec",
    "specification",
    "specification_hash",
    "freeze_to_d24",
    "SpecificationDrift",
    "choose_signal_gb",
    "response_latency_ms",
    "abandons",
    "stated_vs_revealed",
]

SIGNALS: tuple[str, ...] = ("SO", "RC", "CP", "AL")
#: MIMIC's eight QANDA category codes, from ``config/app.php``.
CATEGORIES: tuple[str, ...] = ("ERF", "CMF", "INM", "TRC", "DAP", "DER", "AWU", "CBN")

Mode = Literal["stated", "revealed"]


class SpecificationDrift(RuntimeError):
    """The frozen G-B specification no longer matches the code (5.14 firewall)."""


# --------------------------------------------------------------------------- #
# The frozen specification
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class GBSpec:
    version: str
    base: dict[str, dict[str, float]]
    interactions: dict[str, dict[str, float]]
    comb: dict[str, dict[str, float]]
    context: dict[str, dict[str, float]]
    category: dict[str, dict[str, dict[str, float]]]
    styles: dict[str, float]
    fatigue: dict[str, float]
    stated: dict[str, float]
    latency: dict[str, float]
    abandonment: dict[str, float]
    saturation: dict[str, float]
    citations: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


_SPEC = GBSpec(
    version="G-B/1.0.0",
    # Linear-in-tanh base terms. Signs follow the literature: self-transcendence
    # moves a person away from self-interest (SO) and toward cooperation and
    # altruism; conditional cooperation attaches to reciprocity (RC).
    base={
        "SO": {"trans": -0.95, "comfort": 0.55, "privacy": 0.30, "idvZ": 0.35},
        "RC": {"conditional": 0.80, "instTrust": 0.20, "trans": -0.10},
        "CP": {"trans": 0.60, "env": 0.45, "autonomy": 0.35, "instTrust": 0.25},
        "AL": {"trans": 0.85, "community": 0.70, "env": 0.30},
    },
    # Trait-by-trait products. G-A has none, so these are the clearest single
    # source of misspecification.
    interactions={
        "SO": {"comfort*privacy": 0.30, "idvZ*comfort": 0.25},
        "RC": {"conditional*instTrust": 0.35, "community*conditional": 0.20},
        "CP": {"env*conditional": 0.40, "autonomy*instTrust": 0.30},
        "AL": {"community*instTrust": 0.35, "trans*env": 0.30},
    },
    # COM-B (design 5.13): Capability, Opportunity and Motivation multiply.
    comb={
        "capability": {"education_z": 0.35, "digital_z": 0.30, "intercept": 0.55},
        "opportunity": {"der_owner": 0.45, "time_at_home": 0.30, "tariff_exposure": 0.25, "intercept": 0.40},
        "motivation": {"trans": 0.40, "env": 0.35, "community": 0.25, "intercept": 0.50},
    },
    # Context SCALES the cooperative terms rather than shifting them.
    context={
        "grid_stress": {"cooperative_gain": 0.45, "self_damping": 0.25},
        "visibility": {"cooperative_gain": 0.35, "self_damping": 0.30},
    },
    # Per-category modulation, as multiplicative weights on the base terms.
    # Multiplicative, where G-A's are additive.
    category={
        "CMF": {"SO": {"comfort": 1.80}, "AL": {"trans": 0.70}},
        "ERF": {"CP": {"trans": 1.40}, "AL": {"community": 1.50}, "SO": {"idvZ": 1.60}},
        "INM": {"SO": {"idvZ": 1.70}, "CP": {"env": 1.50}, "RC": {"conditional": 1.40}},
        "TRC": {"CP": {"autonomy": 1.90}, "SO": {"privacy": 1.50}},
        "DAP": {"SO": {"privacy": 2.00}, "CP": {"instTrust": 1.60}},
        "DER": {"CP": {"env": 1.40}, "AL": {"community": 1.40}},
        "AWU": {"CP": {"autonomy": 1.30}, "SO": {"trans": 1.20}},
        "CBN": {"RC": {"conditional": 1.50}, "SO": {"idvZ": 1.80}},
    },
    # Response styles (Meade & Craig; Baumgartner & Steenkamp).
    styles={
        "acquiescence_sd": 0.45,      # tendency to agree with the cooperative option
        "extreme_sd": 0.40,           # tendency to pick a definite rather than a middling option
        "satisficer_flatten": 0.30,   # how far a careless responder moves toward uniform
        "satisficer_noise_sd": 0.55,
    },
    # Fatigue: within a session, and across repeated flexibility asks.
    fatigue={
        "within_session_per_item": 0.035,   # cooperative terms decay per item index
        "within_session_max": 0.30,
        "across_waves_per_ask": 0.012,
        "across_waves_max": 0.35,
        "deliberation_decay_per_item": 0.045,
    },
    # Stated vs revealed (Kormos & Gifford; Sheeran).
    stated={
        "social_desirability_shift_cp": 0.55,
        "social_desirability_shift_al": 0.45,
        "social_desirability_shift_so": -0.60,
    },
    # Response latency, lognormal (design 5.14).
    latency={
        "log_mu_base": 8.35,          # ~4.2 s median
        "log_sigma": 0.52,
        "age_per_decade": 0.085,      # older respondents slower
        "early_item_bonus": 0.22,     # first items slower
        "satisficer_factor": -0.55,   # careless responders much faster
        "deliberation_factor": 0.30,
    },
    abandonment={
        "base_per_item": 0.004,
        "satisficer_multiplier": 2.6,
        "privacy_multiplier": 1.4,
        "late_item_multiplier": 1.8,
    },
    saturation={"tanh_scale": 1.25},
    citations={
        "trans/community/env": "Schwartz values; Van Lange SVO; Zelezny gender",
        "conditional": "Fischbacher, Gachter & Fehr conditional cooperation",
        "comfort": "ASHRAE 55 / ISO 7730 / EN 16798-1 adaptive comfort",
        "privacy/instTrust": "Delhey & Newton social trust; MIMIC Data & Privacy bank",
        "COM-B": "Michie, van Stralen & West COM-B",
        "styles": "Meade & Craig careless responding; Baumgartner & Steenkamp response styles",
        "stated_gap": "Kormos & Gifford; Sheeran intention-behaviour gap",
        "visibility": "Bateson et al. watching eyes; Cialdini focus theory of norms",
        "fatigue": "design 5.3 'fatigue after repeated flexibility asks'",
    },
)


def specification() -> GBSpec:
    return _SPEC


def specification_hash() -> str:
    return hash_json(_SPEC.as_dict())


def freeze_to_d24(path) -> dict[str, Any]:
    """Write the frozen G-B specification into the evidence view (D24).

    Design 5.14's firewall: the specification is frozen **before** any MIMIC
    estimator runs on its output.  Writing it here, and checking it on every
    run, is what makes that a mechanism rather than an intention.
    """
    import json
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "dataset": "D24 calibration_targets / G-B willingness specification",
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
        "design_ref": "5.14 independence protocol, specification firewall",
        "generator": "G-B (HRSD willingness model)",
        "independent_of": "G-A (MIMIC chooseSignal)",
        "structural_differences_from_g_a": [
            "saturating (tanh) utility rather than linear logits",
            "trait-by-trait interaction terms, which G-A has none of",
            "multiplicative COM-B gating (capability x opportunity x motivation)",
            "context scales the cooperative terms rather than shifting them by a constant",
            "acquiescence and extreme-responding styles, independent of the traits",
            "within-session and across-wave fatigue",
            "separate stated and revealed quantities, linked by stated_gap",
        ],
        "specification": _SPEC.as_dict(),
        "specification_hash": specification_hash(),
        "frozen_at": None,  # filled below
        "evidence_tag": "[A] priors from cited literature; unvalidated until FlexSense data (K04, K15)",
    }
    import time

    doc["frozen_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if p.is_file():
        existing = json.loads(p.read_text(encoding="utf-8"))
        if existing.get("specification_hash") != doc["specification_hash"]:
            raise SpecificationDrift(
                f"the frozen G-B specification at {p} has hash "
                f"{existing.get('specification_hash', '')[:16]}... but the code now "
                f"produces {doc['specification_hash'][:16]}.... Design 5.14's "
                f"firewall requires the specification to be frozen BEFORE any "
                f"MIMIC estimator runs on its output, and any later change to be "
                f"logged in the review log with a reason. Log the change, then "
                f"delete the frozen file deliberately to re-freeze."
            )
        return existing
    p.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return doc


def assert_frozen(path) -> str:
    """Refuse to run if the spec on disk and the code disagree."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        raise SpecificationDrift(
            f"no frozen G-B specification at {p}; design 5.14 requires it to be "
            f"frozen before any MIMIC estimator is run. Call freeze_to_d24 first."
        )
    on_disk = json.loads(p.read_text(encoding="utf-8")).get("specification_hash")
    now = specification_hash()
    if on_disk != now:
        raise SpecificationDrift(
            f"frozen G-B hash {str(on_disk)[:16]}... != code hash {now[:16]}..."
        )
    return now


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #

def _sat(x: float) -> float:
    """Saturating transform.  The first structural break from G-A."""
    return math.tanh(x / _SPEC.saturation["tanh_scale"])


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclasses.dataclass
class Context:
    """What the person is being asked, and under what conditions."""

    category: str
    #: MIMIC's context key: 'a' normal, 'b' higher pressure / observability.
    context_key: str = "a"
    grid_stress: float = 0.0        # 0 to 1
    visibility: float = 0.0         # 0 to 1, visible to neighbours
    reward: float = 0.0             # 0 to 1, monetary incentive offered
    comfort_cost: float = 0.0       # 0 to 1, how much comfort is at stake
    item_index: int = 0             # position in the session, 0-based
    asks_seen_before: int = 0       # across-wave flexibility-ask count
    der_owner: float = 0.0          # 0 to 1, share of DER classes owned
    time_at_home: float = 0.5       # 0 to 1, opportunity
    tariff_exposure: float = 0.0    # 0 to 1


def _comb_gate(traits: dict[str, float], ctx: Context) -> dict[str, float]:
    """Capability x Opportunity x Motivation, multiplicatively (design 5.13).

    COM-B's point is that willing people still do not act when capability or
    opportunity is missing, and no additive model can express that: in an
    additive logit, enough motivation always compensates for no opportunity.
    """
    c = _SPEC.comb
    cap = _logistic(
        c["capability"]["intercept"]
        + c["capability"]["education_z"] * traits.get("education_z", 0.0)
        + c["capability"]["digital_z"] * traits.get("digital_z", 0.0)
    )
    opp = _logistic(
        c["opportunity"]["intercept"]
        + c["opportunity"]["der_owner"] * ctx.der_owner
        + c["opportunity"]["time_at_home"] * ctx.time_at_home
        + c["opportunity"]["tariff_exposure"] * ctx.tariff_exposure
    )
    mot = _logistic(
        c["motivation"]["intercept"]
        + c["motivation"]["trans"] * _sat(traits.get("trans", 0.0))
        + c["motivation"]["env"] * _sat(traits.get("env", 0.0))
        + c["motivation"]["community"] * _sat(traits.get("community", 0.0))
    )
    return {"capability": cap, "opportunity": opp, "motivation": mot,
            "gate": cap * opp * mot}


def _utilities(
    traits: dict[str, float],
    ctx: Context,
    *,
    mode: Mode,
    style_acq: float,
    style_ext: float,
    planted_position_bias: float = 0.0,
    display_positions: dict[str, int] | None = None,
) -> dict[str, float]:
    """Utility of each signal.  The heart of G-B."""
    spec = _SPEC
    cat_mod = spec.category.get(ctx.category, {})
    u: dict[str, float] = {}

    for sig in SIGNALS:
        total = 0.0
        # -- saturating base terms, with multiplicative category modulation ---
        for trait, coef in spec.base[sig].items():
            w = cat_mod.get(sig, {}).get(trait, 1.0)
            total += coef * w * _sat(traits.get(trait, 0.0))
        # -- trait interactions ------------------------------------------------
        for key, coef in spec.interactions[sig].items():
            a, b = key.split("*")
            total += coef * _sat(traits.get(a, 0.0)) * _sat(traits.get(b, 0.0))
        u[sig] = total

    # -- COM-B gate on the cooperative signals -----------------------------
    gate = _comb_gate(traits, ctx)["gate"]
    for sig in ("CP", "AL", "RC"):
        u[sig] *= 0.5 + 1.5 * gate
    # Low capability/opportunity pushes toward self-interest, which is the
    # behavioural consequence COM-B describes.
    u["SO"] += 0.60 * (1.0 - gate)

    # -- context, multiplicatively -----------------------------------------
    cx = spec.context
    coop_scale = (
        1.0
        + cx["grid_stress"]["cooperative_gain"] * ctx.grid_stress
        + cx["visibility"]["cooperative_gain"] * ctx.visibility
    )
    self_damp = (
        1.0
        - cx["grid_stress"]["self_damping"] * ctx.grid_stress
        - cx["visibility"]["self_damping"] * ctx.visibility
    )
    for sig in ("CP", "AL"):
        u[sig] *= coop_scale
    u["SO"] *= max(self_damp, 0.1)

    # Reward raises SO for individualists and RC for conditional cooperators,
    # and crowds out intrinsic CP/AL (self-determination theory, design 5.13).
    u["SO"] += 0.40 * ctx.reward * max(_sat(traits.get("idvZ", 0.0)), 0.0)
    u["RC"] += 0.35 * ctx.reward * _sat(traits.get("conditional", 0.0))
    crowding = 0.25 * ctx.reward * max(_sat(traits.get("trans", 0.0)), 0.0)
    u["CP"] -= crowding
    u["AL"] -= crowding

    # Comfort at stake pushes toward protecting it.
    u["SO"] += 0.70 * ctx.comfort_cost * max(_sat(traits.get("comfort", 0.0)), 0.0)

    # -- fatigue ------------------------------------------------------------
    f = spec.fatigue
    within = min(f["within_session_per_item"] * ctx.item_index, f["within_session_max"])
    across = min(f["across_waves_per_ask"] * ctx.asks_seen_before, f["across_waves_max"])
    decay = 1.0 - within - across
    for sig in ("CP", "AL"):
        u[sig] *= max(decay, 0.25)
    u["SO"] += 0.5 * (within + across)

    # -- response styles ----------------------------------------------------
    # Acquiescence: a tendency to agree with the cooperative framing, regardless
    # of traits. Extreme responding: a tendency toward definite options (SO or
    # AL) over middling ones (RC, CP).
    u["CP"] += style_acq * 0.5
    u["AL"] += style_acq * 0.5
    u["SO"] += style_ext * 0.5
    u["AL"] += style_ext * 0.5
    u["RC"] -= style_ext * 0.4
    u["CP"] -= style_ext * 0.3

    # -- stated vs revealed -------------------------------------------------
    if mode == "stated":
        gap = float(traits.get("stated_gap", 0.0))
        s = spec.stated
        u["CP"] += s["social_desirability_shift_cp"] * gap
        u["AL"] += s["social_desirability_shift_al"] * gap
        u["SO"] += s["social_desirability_shift_so"] * gap

    # -- T10 only: planted position bias -----------------------------------
    # Design 5.14: the willingness model is applied "never to screen position
    # (position bias is planted only in test mode T10)". So this term is zero
    # unless a test deliberately plants it.
    if planted_position_bias and display_positions:
        for sig, pos in display_positions.items():
            if sig in u:
                u[sig] += planted_position_bias * (1.0 - pos / max(len(display_positions) - 1, 1))

    return u


def choose_signal_gb(
    traits: dict[str, float],
    ctx: Context,
    gen: np.random.Generator,
    *,
    mode: Mode = "stated",
    planted_position_bias: float = 0.0,
    display_positions: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Choose one of SO / RC / CP / AL, and report how.

    Returns the chosen signal, the probability vector, and the intermediate
    quantities, so D26 can record what truth was planted for each response.
    """
    spec = _SPEC
    style_acq = float(gen.normal(0.0, spec.styles["acquiescence_sd"]))
    style_ext = float(gen.normal(0.0, spec.styles["extreme_sd"]))

    u = _utilities(
        traits, ctx, mode=mode, style_acq=style_acq, style_ext=style_ext,
        planted_position_bias=planted_position_bias,
        display_positions=display_positions,
    )

    satisficer = bool(traits.get("satisficer", 0))
    if satisficer:
        # Flatten toward uniform and add noise. The *form* matches G-A's
        # treatment of careless responders because that is a measurement
        # property rather than a behavioural mechanism, but the coefficient
        # differs and is part of the frozen spec.
        flat = spec.styles["satisficer_flatten"]
        noise = spec.styles["satisficer_noise_sd"]
        u = {k: flat * v + float(gen.normal(0.0, noise)) for k, v in u.items()}

    keys = list(SIGNALS)
    arr = np.array([u[k] for k in keys], dtype=np.float64)
    arr -= arr.max()
    p = np.exp(arr)
    p = p / p.sum()
    chosen = str(gen.choice(keys, p=p))

    # Bounded rationality: a satisficer with low attention may take the first
    # acceptable option rather than sampling from the full distribution. This is
    # a second, distinct departure from G-A, which always samples the softmax.
    deliberated = True
    attention = float(traits.get("attention", 0.6))
    decay = max(
        0.0, 1.0 - spec.fatigue["deliberation_decay_per_item"] * ctx.item_index
    )
    if float(gen.random()) > attention * decay:
        deliberated = False
        # "First acceptable": the first signal, in canonical order, whose
        # utility is above the person's own mean utility.
        mean_u = float(arr.mean())
        for k, val in zip(keys, arr):
            if val >= mean_u:
                chosen = k
                break

    return {
        "chosen_signal": chosen,
        "probabilities": {k: float(v) for k, v in zip(keys, p)},
        "utilities": {k: float(u[k]) for k in keys},
        "mode": mode,
        "deliberated": deliberated,
        "style_acquiescence": style_acq,
        "style_extreme": style_ext,
        "comb": _comb_gate(traits, ctx),
        "spec_version": spec.version,
    }


def stated_vs_revealed(
    traits: dict[str, float], ctx: Context, gen: np.random.Generator
) -> dict[str, Any]:
    """Both quantities for the same person and context (design 5.13).

    The gap between them is what BNIT would face if it "surveyed" Baile Nua, and
    T6 can only ever show that MIMIC recovers the link HRSD planted - never that
    the link exists in people (design 5.14, T6 is internal consistency only).
    """
    stated = choose_signal_gb(traits, ctx, gen, mode="stated")
    revealed = choose_signal_gb(traits, ctx, gen, mode="revealed")
    return {
        "stated": stated,
        "revealed": revealed,
        "agree": stated["chosen_signal"] == revealed["chosen_signal"],
        "stated_gap": float(traits.get("stated_gap", 0.0)),
    }


def response_latency_ms(
    traits: dict[str, float], ctx: Context, gen: np.random.Generator, *, deliberated: bool
) -> int:
    """Lognormal latency: slower with age and on early items, faster for satisficers."""
    L = _SPEC.latency
    mu = L["log_mu_base"]
    age = float(traits.get("age", 45.0))
    mu += L["age_per_decade"] * (age - 45.0) / 10.0
    if ctx.item_index < 3:
        mu += L["early_item_bonus"]
    if traits.get("satisficer"):
        mu += L["satisficer_factor"]
    if deliberated:
        mu += L["deliberation_factor"]
    ms = float(gen.lognormal(mean=mu, sigma=L["log_sigma"]))
    return int(min(max(ms, 350.0), 600_000.0))


def abandons(
    traits: dict[str, float], ctx: Context, gen: np.random.Generator, session_length: int
) -> bool:
    """Whether the participant abandons at this item (design 5.14 'realistic abandonment')."""
    A = _SPEC.abandonment
    p = A["base_per_item"]
    if traits.get("satisficer"):
        p *= A["satisficer_multiplier"]
    if float(traits.get("privacy", 0.0)) > 0.8:
        p *= A["privacy_multiplier"]
    if ctx.item_index >= session_length - 3:
        p *= A["late_item_multiplier"]
    return bool(gen.random() < p)
