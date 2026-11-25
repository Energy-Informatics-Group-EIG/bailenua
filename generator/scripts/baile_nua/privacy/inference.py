"""Design 7.8's inference attacks, measured against Baile Nua's own ground truth.

Four attacks, one per declared target in
:mod:`baile_nua.privacy.threat_model`, each run on every export configuration
in ``edge/export.py``.

**The split is by HOME, and that is the design's own instruction**: "Train an
occupancy classifier ... on the D19 export view of some homes, and test them on
others." It matters more than it looks. A split by *time* within the same homes
would let the attacker learn that particular household's routine, which is the
informed-neighbour class and not the operator class — and would report a far
higher risk than an operator actually has. A split by home measures what the
operator class can do: learn from the population, apply to a stranger.

**Two baselines, because the raw score answers nobody's question.**

*Prior-only.* Predict the training set's base rate for every interval. Its AUC
is 0.5 by construction, and it is the design's reference for the screening
threshold.

*Time-of-day.* Predict the training set's occupancy rate for that
quarter-hour-of-week. This is the **informed neighbour**: somebody who knows
the household's routine already knows the clock. An attack that beats
prior-only but not time-of-day has learned the clock and nothing about the
home, and reporting its raw AUC as a privacy risk would overstate the finding
substantially.

**Why logistic regression and not something stronger.** Two reasons, and the
second is the real one. First, the design's attacks are "known to reveal
presence and routines", and the finding of interest is whether the signal is
*there*, not how well a large model can be made to fit. Second and decisively:
a weak attacker gives a **lower bound** on risk, and a lower bound is the
honest direction for a privacy result. A failing result from a weak attacker is
strong evidence of risk; a passing result from a weak attacker is weak evidence
of safety, and this module says so in its own output rather than letting a
reader assume otherwise. ``ATTACK_STRENGTH_CAVEAT`` is in every record.

**Utility cost is reported alongside.** Design 7.8 requires "the utility cost
of each mitigation (settlement and flexibility-estimate accuracy)", because a
configuration that leaks nothing by carrying nothing is not a mitigation but a
refusal. Settlement accuracy is measured as the error in the home's billed
energy under the configuration against the true metered energy.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

__all__ = [
    "ATTACKS",
    "ATTACK_STRENGTH_CAVEAT",
    "InferenceError",
    "auc",
    "auc_ci",
    "run_attacks",
]

ATTACKS: tuple[str, ...] = (
    "occupancy_classifier",
    "holiday_detector",
    "household_size_estimator",
    "routine_change_detector",
)

ATTACK_STRENGTH_CAVEAT = (
    "These attacks are regularised logistic and linear models on interval "
    "features. A WEAK attacker bounds the risk from BELOW, which is the "
    "honest direction for a privacy result but cuts only one way: a FAILING "
    "result here is strong evidence of risk, and a PASSING result is weak "
    "evidence of safety. A stronger attacker - a sequence model with access "
    "to years of linked releases - would do better, and nothing here bounds "
    "by how much."
)


class InferenceError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def auc(y: np.ndarray, score: np.ndarray) -> float:
    """ROC AUC by the rank identity, ties shared.

    Written out rather than imported so the figure does not depend on a
    library's tie convention: with coarse scores - a baseline that predicts one
    of 672 values - ties are the normal case, not an edge case, and a
    convention that breaks them in the attacker's favour would inflate every
    baseline.
    """
    y = np.asarray(y).astype(bool)
    s = np.asarray(score, dtype=np.float64)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=np.float64)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0      # shared mid-rank
        i = j + 1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def auc_ci(y: np.ndarray, score: np.ndarray, *, z: float = 1.96) -> dict[str, float]:
    """AUC with a Hanley-McNeil 95% interval.

    The UPPER bound is what design 7.8's screening threshold is applied to: a
    wide interval whose centre clears 0.60 has not cleared it.
    """
    a = auc(y, score)
    y = np.asarray(y).astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if not np.isfinite(a) or n1 == 0 or n0 == 0:
        return {"auc": a, "lo": float("nan"), "hi": float("nan"),
                "n_pos": n1, "n_neg": n0}
    q1 = a / (2.0 - a)
    q2 = 2.0 * a * a / (1.0 + a)
    var = (a * (1 - a) + (n1 - 1) * (q1 - a * a)
           + (n0 - 1) * (q2 - a * a)) / (n1 * n0)
    se = math.sqrt(max(var, 0.0))
    return {"auc": round(a, 4), "lo": round(max(a - z * se, 0.0), 4),
            "hi": round(min(a + z * se, 1.0), 4), "se": round(se, 5),
            "n_pos": n1, "n_neg": n0}


def _fit_logistic(
    X: np.ndarray, y: np.ndarray, *, l2: float = 1.0, iters: int = 200,
) -> np.ndarray:
    """Newton-IRLS logistic regression with an L2 penalty and an intercept.

    Standardised inside, so a feature's scale cannot decide the fit.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    pen = np.eye(Z.shape[1]) * l2
    pen[0, 0] = 0.0                      # never penalise the intercept
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (y - p) - pen @ w
        W = np.clip(p * (1 - p), 1e-8, None)
        H = -(Z.T * W) @ Z - pen
        try:
            step = np.linalg.solve(H, -g)
        except np.linalg.LinAlgError:
            break
        w = w + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return np.concatenate([[mu.size], mu, sd, w])        # packed


def _predict_logistic(packed: np.ndarray, X: np.ndarray) -> np.ndarray:
    k = int(packed[0])
    mu, sd, w = packed[1:1 + k], packed[1 + k:1 + 2 * k], packed[1 + 2 * k:]
    Z = np.column_stack([np.ones(len(X)), (np.asarray(X, float) - mu) / sd])
    return 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))


# --------------------------------------------------------------------------- #
# features
# --------------------------------------------------------------------------- #

def _interval_features(df: Any) -> tuple[np.ndarray, list[str]]:
    """Features an attacker can compute from the export alone.

    Every one is a function of the exported columns and the clock. Nothing
    here touches ground truth - which is the whole point, and is asserted by
    ``test_the_attacker_sees_only_the_export``.
    """
    import pandas as pd

    e = pd.to_numeric(df["import_wh"], errors="coerce").fillna(0.0).to_numpy()
    ts = pd.to_datetime(df["interval_start"], utc=True)
    hour = ts.dt.hour.to_numpy() + ts.dt.minute.to_numpy() / 60.0
    dow = ts.dt.dayofweek.to_numpy()

    # Within-home normalisation: an attacker comparing a big house to a small
    # one learns the house size, not the occupancy, and a model trained on raw
    # watt-hours would score well by learning which homes are large. Dividing
    # by the home's own median removes that and isolates the SHAPE, which is
    # the quantity design 7.8 is about.
    by_home = df.groupby("premises_id")["import_wh"].transform(
        lambda s: pd.to_numeric(s, errors="coerce").median())
    med = np.where(by_home.to_numpy() > 0, by_home.to_numpy(), 1.0)
    rel = e / med

    # Local shape: the change from the previous interval, and the deviation
    # from this home's own level at this time of day.
    g = df.groupby("premises_id")["import_wh"]
    diff = g.diff().fillna(0.0).to_numpy() / med
    roll = g.transform(lambda s: pd.to_numeric(s, errors="coerce")
                       .rolling(6, min_periods=1).mean()).to_numpy() / med

    cols = ["rel_import", "diff", "roll6", "sin_h", "cos_h", "sin_2h",
            "cos_2h", "is_weekend"]
    X = np.column_stack([
        rel, diff, roll,
        np.sin(2 * np.pi * hour / 24.0), np.cos(2 * np.pi * hour / 24.0),
        np.sin(4 * np.pi * hour / 24.0), np.cos(4 * np.pi * hour / 24.0),
        (dow >= 5).astype(np.float64),
    ])
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0), cols


def _slot_of_week(df: Any, *, interval_min: int) -> np.ndarray:
    """Which interval of the week, for the time-of-day baseline."""
    import pandas as pd

    ts = pd.to_datetime(df["interval_start"], utc=True)
    per_day = (24 * 60) // max(interval_min, 1)
    return (ts.dt.dayofweek.to_numpy() * per_day
            + (ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy())
            // max(interval_min, 1))


# --------------------------------------------------------------------------- #
# the attacks
# --------------------------------------------------------------------------- #

def _occupancy_attack(
    train: Any, test: Any, *, interval_min: int,
) -> dict[str, Any]:
    """Design 7.8's headline attack: is anyone at home in this interval."""
    ytr = train["occupied"].to_numpy().astype(bool)
    yte = test["occupied"].to_numpy().astype(bool)
    if ytr.sum() == 0 or (~ytr).sum() == 0 or yte.sum() == 0 or (~yte).sum() == 0:
        return {
            "measured": False,
            "why": (
                "occupancy is constant in the train or test homes, so no "
                "classifier can be scored. This is a property of the window, "
                "not a passing result: a town where everyone is always home "
                "cannot demonstrate that absence is undetectable."
            ),
            "train_occupied_rate": round(float(ytr.mean()), 4) if len(ytr) else None,
            "test_occupied_rate": round(float(yte.mean()), 4) if len(yte) else None,
        }

    Xtr, cols = _interval_features(train)
    Xte, _ = _interval_features(test)
    model = _fit_logistic(Xtr, ytr.astype(float))
    p = _predict_logistic(model, Xte)

    # prior-only: the training base rate, the same for every interval.
    prior = np.full(len(yte), float(ytr.mean()))
    # time-of-day: the training occupancy rate for that slot of the week. The
    # informed-neighbour baseline.
    slot_tr = _slot_of_week(train, interval_min=interval_min)
    slot_te = _slot_of_week(test, interval_min=interval_min)
    rate = {}
    for s in np.unique(slot_tr):
        m = slot_tr == s
        rate[int(s)] = float(ytr[m].mean()) if m.sum() else float(ytr.mean())
    tod = np.array([rate.get(int(s), float(ytr.mean())) for s in slot_te])

    a_model, a_prior, a_tod = (auc_ci(yte, p), auc_ci(yte, prior),
                               auc_ci(yte, tod))
    # Precision and recall at an operational threshold: the attacker calls
    # "absent" where the model is most confident of absence. 0.5 is the
    # textbook threshold and the wrong one for an attacker, who chooses the
    # threshold that serves them - so the top decile of confident-absence is
    # reported too.
    out: dict[str, Any] = {"measured": True, "features": cols}
    for name, thr in (("at_0.5", 0.5),
                      ("top_decile_absence", float(np.quantile(p, 0.10)))):
        called_absent = p <= thr
        tp = int((called_absent & ~yte).sum())
        fp = int((called_absent & yte).sum())
        fn = int((~called_absent & ~yte).sum())
        out[f"absence_{name}"] = {
            "threshold": round(thr, 4),
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "n_called_absent": int(called_absent.sum()),
        }
    out.update({
        "auc_model": a_model,
        "auc_prior_only": a_prior,
        "auc_time_of_day": a_tod,
        "advantage_over_prior": round(a_model["auc"] - a_prior["auc"], 4),
        "advantage_over_time_of_day": round(a_model["auc"] - a_tod["auc"], 4),
        "test_occupied_rate": round(float(yte.mean()), 4),
        "reading": (
            "The advantage over TIME-OF-DAY is the number that bears on the "
            "informed-neighbour class, and it is usually much smaller than "
            "the raw AUC: somebody who knows the routine already knows the "
            "clock. The raw AUC bears on the operator class, which does not "
            "know the household."
        ),
    })
    return out


def _holiday_attack(train: Any, test: Any) -> dict[str, Any]:
    """Absence over a run of days, scored per HOME-DAY rather than per interval.

    Per day because the consequence - burglary timing - follows from
    identifying a day or a week, and a per-interval score would be dominated
    by the many easy night-time intervals of an occupied home.
    """
    import pandas as pd

    def daily(df: Any) -> Any:
        d = df.copy()
        d["day"] = pd.to_datetime(d["interval_start"], utc=True).dt.date
        g = d.groupby(["premises_id", "day"])
        out = g.agg(import_wh=("import_wh", "sum"),
                    peak=("import_wh", "max"),
                    occupied_frac=("occupied", "mean")).reset_index()
        # Relative to the home's own median day: an away day is low FOR THAT
        # HOME, and the absolute level is the house's size.
        out["rel_day"] = out.groupby("premises_id")["import_wh"].transform(
            lambda s: s / max(s.median(), 1e-9))
        out["rel_peak"] = out.groupby("premises_id")["peak"].transform(
            lambda s: s / max(s.median(), 1e-9))
        # Design 7.8's target is an ABSENCE PERIOD: a day with essentially
        # nobody home, not a day somebody stepped out.
        out["away"] = out["occupied_frac"] < 0.25
        return out

    tr, te = daily(train), daily(test)
    if tr["away"].nunique() < 2 or te["away"].nunique() < 2:
        return {
            "measured": False,
            "why": (
                "no away-day in the train or test homes over this window, so "
                "a holiday detector cannot be scored. A 14-day window in "
                "January contains few holidays by construction; this is a "
                "limit of the window, NOT a finding that absence is "
                "undetectable."
            ),
            "train_away_days": int(tr["away"].sum()),
            "test_away_days": int(te["away"].sum()),
        }
    cols = ["rel_day", "rel_peak"]
    model = _fit_logistic(tr[cols].to_numpy(), tr["away"].to_numpy().astype(float))
    p = _predict_logistic(model, te[cols].to_numpy())
    a = auc_ci(te["away"].to_numpy(), p)
    prior = np.full(len(te), float(tr["away"].mean()))
    return {
        "measured": True, "grain": "home-day", "features": cols,
        "auc_model": a, "auc_prior_only": auc_ci(te["away"].to_numpy(), prior),
        "advantage_over_prior": round(a["auc"] - 0.5, 4),
        "n_away_days_in_test": int(te["away"].sum()),
        "n_home_days_in_test": int(len(te)),
        "away_defined_as": "fewer than 25% of the day's intervals occupied",
    }


def _household_size_attack(train: Any, test: Any) -> dict[str, Any]:
    """How many people live here, from the export alone. Linear, scored by MAE.

    Reported against the obvious baseline - predict the training mean - so a
    small error is not mistaken for a successful attack when the population's
    household sizes are narrow anyway.
    """
    def per_home(df: Any) -> Any:
        g = df.groupby("premises_id")
        out = g.agg(mean_wh=("import_wh", "mean"),
                    p95=("import_wh", lambda s: float(np.quantile(s, 0.95))),
                    sd=("import_wh", "std"),
                    total=("import_wh", "sum"),
                    size=("household_size", "first")).reset_index()
        out["sd"] = out["sd"].fillna(0.0)
        return out

    tr, te = per_home(train), per_home(test)
    if tr["size"].isna().any() or te["size"].isna().any():
        raise InferenceError("household_size is missing for some homes")
    cols = ["mean_wh", "p95", "sd", "total"]
    A = np.column_stack([np.ones(len(tr)), tr[cols].to_numpy()])
    coef, *_ = np.linalg.lstsq(A, tr["size"].to_numpy(float), rcond=None)
    pred = np.column_stack([np.ones(len(te)), te[cols].to_numpy()]) @ coef
    truth = te["size"].to_numpy(float)
    base = float(tr["size"].mean())
    mae = float(np.abs(pred - truth).mean())
    mae_base = float(np.abs(base - truth).mean())
    return {
        "measured": True, "grain": "home", "features": cols,
        "n_test_homes": int(len(te)),
        "mae_attack": round(mae, 4),
        "mae_baseline_predict_the_mean": round(mae_base, 4),
        "improvement_over_baseline": round(mae_base - mae, 4),
        "exact_within_half_a_person": round(
            float((np.abs(pred - truth) < 0.5).mean()), 4),
        "reading": (
            "An attack that does not beat 'predict the mean' has learned "
            "nothing about the home. The improvement, not the MAE, is the "
            "privacy-relevant quantity."
        ),
    }


def _routine_change_attack(train: Any, test: Any) -> dict[str, Any]:
    """Has this household's routine changed, from the export alone.

    Both readings of a high score are reported, because they are both true:
    change detection is the task the whole dataset exists to support, and it
    is simultaneously a privacy risk. Reporting only one would be choosing a
    framing.
    """
    import pandas as pd

    def daily(df: Any) -> Any:
        d = df.copy()
        d["day"] = pd.to_datetime(d["interval_start"], utc=True).dt.date
        g = d.groupby(["premises_id", "day"])
        out = g.agg(import_wh=("import_wh", "sum"),
                    occ=("occupied", "mean"),
                    n_people=("household_size", "first")).reset_index()
        out["rel"] = out.groupby("premises_id")["import_wh"].transform(
            lambda s: s / max(s.median(), 1e-9))
        # Truth: the day's occupancy profile departs from this home's own
        # recent norm. A change in the PEOPLE is what D20 labels; within a
        # short window the measurable proxy is a change in the routine.
        out["occ_z"] = out.groupby("premises_id")["occ"].transform(
            lambda s: (s - s.mean()) / (s.std() if s.std() > 1e-9 else 1.0))
        out["changed"] = out["occ_z"].abs() > 1.5
        out["rel_z"] = out.groupby("premises_id")["rel"].transform(
            lambda s: (s - s.mean()) / (s.std() if s.std() > 1e-9 else 1.0))
        return out

    tr, te = daily(train), daily(test)
    if tr["changed"].nunique() < 2 or te["changed"].nunique() < 2:
        return {"measured": False,
                "why": "no routine-change day in train or test over this window"}
    cols = ["rel", "rel_z"]
    model = _fit_logistic(tr[cols].to_numpy(),
                          tr["changed"].to_numpy().astype(float))
    p = _predict_logistic(model, te[cols].to_numpy())
    a = auc_ci(te["changed"].to_numpy(), p)
    return {
        "measured": True, "grain": "home-day", "features": cols,
        "auc_model": a,
        "advantage_over_prior": round(a["auc"] - 0.5, 4),
        "changed_defined_as": (
            "the day's occupied fraction more than 1.5 SD from this home's "
            "own mean over the window"
        ),
        "both_readings": (
            "A high score here is the dataset WORKING - change detection is "
            "what D20's labels exist for - and a privacy risk at the same "
            "time. Neither reading cancels the other and reporting one alone "
            "would be choosing a framing."
        ),
    }


# --------------------------------------------------------------------------- #
# the harness
# --------------------------------------------------------------------------- #

def run_attacks(
    *, frame: Any, config_name: str, interval_min: int,
    train_share: float = 0.6, master_seed: int = 20251010,
) -> dict[str, Any]:
    """Run every attack on one export configuration.

    ``frame`` needs ``premises_id``, ``interval_start``, ``import_wh`` (the
    export) plus ``occupied`` and ``household_size`` (ground truth, used ONLY
    as labels). The split is by home, per design 7.8.
    """
    import pandas as pd

    from baile_nua.privacy import threat_model as tm

    df = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
    needed = {"premises_id", "interval_start", "import_wh", "occupied",
              "household_size"}
    missing = sorted(needed - set(df.columns))
    if missing:
        raise InferenceError(
            f"the attack frame is missing {missing}. `occupied` and "
            f"`household_size` are LABELS and must never be features; "
            f"`import_wh` and `interval_start` are the export."
        )

    homes = sorted(df["premises_id"].astype(str).unique())
    if len(homes) < 4:
        raise InferenceError(
            f"{len(homes)} homes is too few for a by-home split. Design 7.8 "
            f"trains on some homes and tests on others; a split by TIME "
            f"within the same homes would measure the informed-neighbour "
            f"class and report it as the operator class."
        )
    rng = np.random.default_rng(master_seed)
    order = list(homes)
    rng.shuffle(order)
    cut = max(2, int(round(len(order) * train_share)))
    train_homes, test_homes = set(order[:cut]), set(order[cut:])
    if not test_homes:
        raise InferenceError("the split left no test homes")

    pid = df["premises_id"].astype(str)
    train = df[pid.isin(train_homes)].copy()
    test = df[pid.isin(test_homes)].copy()

    results = {
        "occupancy_classifier": _occupancy_attack(
            train, test, interval_min=interval_min),
        "holiday_detector": _holiday_attack(train, test),
        "household_size_estimator": _household_size_attack(train, test),
        "routine_change_detector": _routine_change_attack(train, test),
    }

    occ = results["occupancy_classifier"]
    screen: dict[str, Any]
    if not occ.get("measured"):
        screen = {
            "applicable": False,
            "why": occ.get("why"),
            "verdict": "NOT EVALUABLE",
            "not_the_same_as_passing": (
                "A configuration whose occupancy attack could not be scored "
                "has not cleared the screening threshold; it has not been "
                "tested against it."
            ),
        }
    else:
        hi = occ["auc_model"]["hi"]
        screen = {
            "applicable": True,
            "threshold": tm.SCREENING_AUC,
            "applied_to": "the UPPER 95% bound, not the point estimate",
            "auc_upper_95": hi,
            "clears_screening": bool(hi <= tm.SCREENING_AUC),
            "verdict": ("CLEARS SCREENING" if hi <= tm.SCREENING_AUC
                        else "FAILS SCREENING"),
            "screening_is_not_approval": tm.threat_model()[
                "screening_is_not_a_pass_mark"],
        }

    return {
        "config": config_name,
        "interval_min": interval_min,
        "n_homes": len(homes),
        "n_train_homes": len(train_homes),
        "n_test_homes": len(test_homes),
        "split": "by HOME, per design 7.8",
        "why_by_home": (
            "A split by TIME within the same homes lets the attacker learn "
            "that household's own routine, which is the informed-neighbour "
            "class, and would report it as the operator class - overstating "
            "what an operator can do to a stranger."
        ),
        "n_rows": int(len(df)),
        "attacks": results,
        "attacks_run": ATTACKS,
        "unattacked_declared_targets": tm.unattacked_targets(ATTACKS),
        "screening": screen,
        "attack_strength_caveat": ATTACK_STRENGTH_CAVEAT,
        "claim_boundary": tm.CLAIM_BOUNDARY,
    }
