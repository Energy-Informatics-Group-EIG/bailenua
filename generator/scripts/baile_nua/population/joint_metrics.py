"""Joint and spatial fidelity metrics for the U03 comparison (design 5.2 step 2).

Review 2 finding A4, accepted into revision 3:

    Marginals don't prove joint or spatial representativeness.

and design 5.2 step 2:

    Validation covers marginals and also the joint and spatial structure:
    household composition by age of members, age-economic status-tenure
    dependencies, car ownership by household type, commuting accessibility, and
    spatial segregation indices across estates.  The method with the smaller
    joint-distribution error is recommended.

**What the public data can and cannot support.**  SAPS publishes marginals per
small area; it publishes no individual-level cross-tabulations.  So a true joint
distribution for Cobh does not exist in the inputs and cannot be the yardstick -
claiming to measure "joint-distribution error" against a joint distribution
nobody has would be the kind of unfalsifiable check design 7 forbids.

What does exist is the **between-area joint structure**.  Within a single small
area the marginal categories co-occur, so across Cobh's 53 areas there is a real,
measurable association between, say, the share of one-person households and the
share of residents aged 65+.  That association is precisely what the two U03
methods treat differently, and it is what the dependencies named in step 2 reduce
to when the only unit available is the small area.  Every metric below is
therefore stated as a between-area quantity, and the E1 report says so rather
than implying individual-level validation.

Three families of metric:

``marginal_error``   per-marginal total-variation distance and max standardised
                     deviation against full Cobh.
``joint_error``      distance between the cross-marginal association matrices,
                     over the specific dependency pairs design 5.2 step 2 names.
``spatial_error``    Moran's I (spatial autocorrelation), the dissimilarity index
                     (segregation), and spatial coverage.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from baile_nua.population.saps import Marginal

__all__ = [
    "DEPENDENCY_PAIRS",
    "SEGREGATION_VARIABLES",
    "marginal_error",
    "joint_error",
    "spatial_error",
    "compare_methods",
    "shares_matrix",
    "morans_i",
    "dissimilarity_index",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def shares_matrix(by_small_area: pd.DataFrame) -> pd.DataFrame:
    """Row-normalise an area x category count table to within-area shares."""
    tot = by_small_area.sum(axis=1).replace(0, np.nan)
    return by_small_area.div(tot, axis=0).fillna(0.0)


def _series(frame: pd.DataFrame, marginal_key: str, categories: tuple[str, ...]) -> pd.Series:
    """Share of the named categories within a marginal, per small area."""
    sh = shares_matrix(frame)
    present = [c for c in categories if c in sh.columns]
    if not present:
        raise KeyError(f"{marginal_key}: none of {categories} present in {list(sh.columns)[:8]}")
    return sh[present].sum(axis=1)


#: Age bands, assembled from the SAPS age-by-sex category labels, which are of
#: the form ``"<band>_<M|F>"`` (for example ``"0_M"``, ``"65_69_F"``).
def _age_categories(columns: list[str], lo: int, hi: int) -> tuple[str, ...]:
    out = []
    for c in columns:
        band = c.rsplit("_", 1)[0]
        first = band.split("_")[0]
        try:
            start = int(first.replace("GE", "").replace("OVER", ""))
        except ValueError:
            continue
        if lo <= start <= hi:
            out.append(c)
    return tuple(out)


#: The dependencies design 5.2 step 2 names, expressed as between-area
#: association pairs.  Each entry is
#: ``(label, (marginal_a, categories_a), (marginal_b, categories_b))``.
#: ``categories = ()`` means "resolve from the age labels" via :func:`_age_categories`.
DEPENDENCY_PAIRS: tuple[tuple[str, tuple[str, Any], tuple[str, Any]], ...] = (
    # "household composition by age of members"
    (
        "one-person households vs residents aged 65+",
        ("household_size", ("1",)),
        ("age_by_sex", ("AGE65+",)),
    ),
    (
        "households with children vs residents aged 0-14",
        (
            "household_type",
            (
                "married couple with children",
                "cohabiting couple with children",
                "one parent (father) with children",
                "one parent (mother) with children",
                "couple with children and others",
                "one parent (father) with children and others",
                "one parent (mother) with children and others",
            ),
        ),
        ("age_by_sex", ("AGE0-14",)),
    ),
    # "age-economic status-tenure dependencies"
    (
        "retired residents vs owner-occupied no mortgage",
        ("economic_status", ("retired",)),
        ("tenure", ("owner-occupied no mortgage",)),
    ),
    (
        "at-work residents vs owner-occupied with mortgage",
        ("economic_status", ("at work",)),
        ("tenure", ("owner-occupied with mortgage",)),
    ),
    (
        "unemployment vs social renting",
        ("economic_status", ("short-term unemployed", "long-term unemployed",
                             "looking for first regular job")),
        ("tenure", ("rented social",)),
    ),
    # "car ownership by household type"
    (
        "no-car households vs one-person households",
        ("car_availability", ("0",)),
        ("household_size", ("1",)),
    ),
    (
        "two-or-more-car households vs households of 4+",
        ("car_availability", ("2", "3", "4+")),
        ("household_size", ("4", "5", "6", "7", "8+")),
    ),
    # "commuting accessibility"
    (
        "rail commuting vs at-work residents",
        ("travel_mode_work", ("rail",)),
        ("economic_status", ("at work",)),
    ),
    (
        "early departure (before 07:30) vs car driving to work",
        ("time_leaving_home", ("before 06:30", "06:30-07:00", "07:01-07:30")),
        ("travel_mode_work", ("car driver",)),
    ),
    (
        "working from home vs professional occupations",
        ("working_from_home", ("works from home",)),
        ("occupation", ("managers, directors and senior officials", "professional",
                        "associate professional and technical")),
    ),
    # dwelling and heating structure
    (
        "apartments vs one-person households",
        ("accommodation_type", ("flat or apartment",)),
        ("household_size", ("1",)),
    ),
    (
        "pre-1919 dwellings vs oil heating",
        ("year_built", ("pre 1919",)),
        ("central_heating", ("oil",)),
    ),
    # nationality mechanisms (design 5.8), kept to tenure and household size as
    # the stereotype guard requires - no direct per-group behaviour multiplier
    (
        "non-Irish-born residents vs private renting",
        ("place_of_birth", ("UK", "PL", "IN", "EU27_other", "rest_of_world")),
        ("tenure", ("rented private",)),
    ),
)

#: Variables whose spatial segregation across estates design 5.2 step 2 names.
SEGREGATION_VARIABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("social renting", "tenure", ("rented social",)),
    ("private renting", "tenure", ("rented private",)),
    ("non-Irish-born", "place_of_birth", ("UK", "PL", "IN", "EU27_other", "rest_of_world")),
    ("one-person households", "household_size", ("1",)),
    ("households of 4+", "household_size", ("4", "5", "6", "7", "8+")),
    ("no-car households", "car_availability", ("0",)),
    ("apartments", "accommodation_type", ("flat or apartment",)),
)


def _resolve(marginals: dict[str, pd.DataFrame], key: str, cats: Any) -> pd.Series:
    """Resolve one side of a dependency pair into a per-area share series."""
    frame = marginals[key]
    if key == "age_by_sex" and isinstance(cats, tuple) and cats and cats[0].startswith("AGE"):
        spec = cats[0]
        cols = list(frame.columns)
        if spec == "AGE65+":
            resolved = _age_categories(cols, 65, 200)
        elif spec == "AGE0-14":
            resolved = _age_categories(cols, 0, 14)
        else:
            raise KeyError(f"unknown age spec {spec}")
        return _series(frame, key, resolved)
    return _series(frame, key, tuple(cats))


# --------------------------------------------------------------------------- #
# 1. Marginal error
# --------------------------------------------------------------------------- #

def marginal_error(
    reference: dict[str, Marginal], scaled_town: dict[str, pd.Series]
) -> pd.DataFrame:
    """Per-marginal total-variation distance and max standardised deviation.

    The standardised deviation uses the **multinomial sampling standard error**
    at the scaled sample size, which is what design 12 R04 means by "within the
    sampling-error band": a town of 2,931 people simply cannot reproduce a
    14,148-person distribution more precisely than its own sample size allows,
    and judging it against a tighter band would be judging it against noise.
    """
    rows = []
    for key, m in reference.items():
        ref = m.town_total.astype(float)
        ref_share = ref / ref.sum() if ref.sum() else ref
        got = scaled_town[key].reindex(ref.index).fillna(0).astype(float)
        n = got.sum()
        got_share = got / n if n else got

        tv = 0.5 * float(np.abs(got_share - ref_share).sum())
        # Standardised deviation per category, against multinomial SE at size n.
        with np.errstate(divide="ignore", invalid="ignore"):
            se = np.sqrt(ref_share * (1.0 - ref_share) / n) if n else np.full(len(ref), np.nan)
            z = np.where(se > 0, (got_share - ref_share) / se, 0.0)
        rows.append(
            {
                "marginal": key,
                "unit": m.spec.unit,
                "n_categories": int(len(ref)),
                "n_scaled": int(n),
                "total_variation_distance": tv,
                "max_abs_z": float(np.nanmax(np.abs(z))) if n else float("nan"),
                "mean_abs_z": float(np.nanmean(np.abs(z))) if n else float("nan"),
                "chi2_per_category": float(
                    np.nansum(np.where(ref_share > 0, (got_share - ref_share) ** 2 / ref_share, 0.0))
                    * n / max(len(ref), 1)
                ),
            }
        )
    return pd.DataFrame(rows).set_index("marginal").sort_index()


# --------------------------------------------------------------------------- #
# 2. Joint error
# --------------------------------------------------------------------------- #

def joint_error(
    reference_sa: dict[str, pd.DataFrame], scaled_sa: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Between-area association for each dependency pair, reference vs scaled.

    Association is Spearman rank correlation across small areas.  Rank rather
    than Pearson because several of these shares are strongly skewed (one area is
    74% social renting) and a single area would otherwise dominate the statistic.
    """
    rows = []
    for label, (ka, ca), (kb, cb) in DEPENDENCY_PAIRS:
        try:
            ra, rb = _resolve(reference_sa, ka, ca), _resolve(reference_sa, kb, cb)
            sa, sb = _resolve(scaled_sa, ka, ca), _resolve(scaled_sa, kb, cb)
        except KeyError as exc:
            rows.append({"dependency": label, "error": str(exc)})
            continue
        ref_rho = _spearman(ra, rb)
        # The scaled town is compared on ITS OWN areas: method (a) keeps a
        # subset, and asking it about areas it does not contain would measure
        # coverage twice (coverage is reported separately, in spatial_error).
        common = sa.index.intersection(sb.index)
        got_rho = _spearman(sa.loc[common], sb.loc[common])
        rows.append(
            {
                "dependency": label,
                "reference_spearman": ref_rho,
                "scaled_spearman": got_rho,
                "abs_difference": abs(got_rho - ref_rho)
                if not (math.isnan(ref_rho) or math.isnan(got_rho))
                else float("nan"),
                "n_areas_scaled": int(len(common)),
            }
        )
    return pd.DataFrame(rows).set_index("dependency")


def _spearman(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 3 or a.nunique() < 2 or b.nunique() < 2:
        return float("nan")
    ra, rb = a.rank(), b.rank()
    ra, rb = ra - ra.mean(), rb - rb.mean()
    denom = math.sqrt(float((ra**2).sum()) * float((rb**2).sum()))
    return float((ra * rb).sum() / denom) if denom else float("nan")


# --------------------------------------------------------------------------- #
# 3. Spatial error
# --------------------------------------------------------------------------- #

def morans_i(values: pd.Series, centroids: pd.DataFrame) -> float:
    """Moran's I with row-standardised inverse-distance weights.

    Measures whether similar values cluster in space.  Preserving it is what
    design 5.2 step 2 means by preserving spatial structure: a method that keeps
    every area's share but scatters them would score the same on every marginal
    and fail here.
    """
    idx = [i for i in values.index if i in centroids.index]
    if len(idx) < 4:
        return float("nan")
    v = values.loc[idx].to_numpy(dtype=float)
    xy = centroids.loc[idx, ["centroid_lon", "centroid_lat"]].to_numpy(dtype=float)
    n = len(idx)
    d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2))
    with np.errstate(divide="ignore"):
        w = np.where(d > 0, 1.0 / d, 0.0)
    np.fill_diagonal(w, 0.0)
    rs = w.sum(axis=1, keepdims=True)
    w = np.divide(w, rs, out=np.zeros_like(w), where=rs > 0)
    z = v - v.mean()
    denom = float((z**2).sum())
    if denom == 0.0:
        return float("nan")
    num = float(z @ (w @ z))
    # Row-standardised weights sum to n, so the n/S0 factor is 1.
    return num / denom


def dissimilarity_index(minority: pd.Series, total: pd.Series) -> float:
    """Index of dissimilarity D: the segregation index design 5.2 step 2 names.

    D is the share of the minority group that would have to move for every area
    to have the town-wide proportion.  0 = evenly spread, 1 = complete
    separation.
    """
    idx = minority.index.intersection(total.index)
    m = minority.loc[idx].astype(float)
    t = total.loc[idx].astype(float)
    maj = t - m
    M, J = float(m.sum()), float(maj.sum())
    if M <= 0 or J <= 0:
        return float("nan")
    return float(0.5 * np.abs(m / M - maj / J).sum())


def spatial_error(
    reference_sa: dict[str, pd.DataFrame],
    scaled_sa: dict[str, pd.DataFrame],
    centroids: pd.DataFrame,
) -> pd.DataFrame:
    """Moran's I and dissimilarity for each segregation variable, plus coverage."""
    rows = []
    for label, key, cats in SEGREGATION_VARIABLES:
        ref_frame, got_frame = reference_sa[key], scaled_sa[key]
        ref_share = _resolve(reference_sa, key, cats)
        got_share = _resolve(scaled_sa, key, cats)
        ref_count = ref_frame[[c for c in cats if c in ref_frame.columns]].sum(axis=1)
        got_count = got_frame[[c for c in cats if c in got_frame.columns]].sum(axis=1)

        ref_i = morans_i(ref_share, centroids)
        got_i = morans_i(got_share, centroids)
        ref_d = dissimilarity_index(ref_count, ref_frame.sum(axis=1))
        got_d = dissimilarity_index(got_count, got_frame.sum(axis=1))
        rows.append(
            {
                "variable": label,
                "reference_morans_i": ref_i,
                "scaled_morans_i": got_i,
                "morans_i_abs_difference": abs(got_i - ref_i)
                if not (math.isnan(ref_i) or math.isnan(got_i))
                else float("nan"),
                "reference_dissimilarity": ref_d,
                "scaled_dissimilarity": got_d,
                "dissimilarity_abs_difference": abs(got_d - ref_d)
                if not (math.isnan(ref_d) or math.isnan(got_d))
                else float("nan"),
            }
        )
    return pd.DataFrame(rows).set_index("variable")


# --------------------------------------------------------------------------- #
# The U03 comparison
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class MethodScore:
    method: str
    marginal: pd.DataFrame
    joint: pd.DataFrame
    spatial: pd.DataFrame
    summary: dict[str, Any]


def compare_methods(
    reference: dict[str, Marginal],
    plans: dict[str, Any],
    centroids: pd.DataFrame,
) -> tuple[dict[str, MethodScore], pd.DataFrame, dict[str, Any]]:
    """Score both U03 candidates on marginal, joint and spatial error.

    Returns ``(per-method detail, the comparison table, the recommendation)``.
    The recommendation applies design 5.2 step 2's own rule - "the method with
    the smaller joint-distribution error is recommended" - with spatial error as
    the stated tie-break, and it reports the numbers that produced it rather than
    only the verdict.
    """
    reference_sa = {k: m.by_small_area for k, m in reference.items()}
    scores: dict[str, MethodScore] = {}
    rows = []
    for name, plan in plans.items():
        marg = marginal_error(reference, plan.town_marginals)
        joint = joint_error(reference_sa, plan.marginals)
        spat = spatial_error(reference_sa, plan.marginals, centroids)
        coverage = len(plan.areas_kept) / len(reference["household_size"].by_small_area)
        summary = {
            "method": name,
            "n_people": plan.n_people,
            "n_households": plan.n_households,
            "meets_r03_ranges": plan.meets_r03,
            "n_areas_kept": len(plan.areas_kept),
            "spatial_coverage": round(coverage, 4),
            "marginal_mean_tvd": float(marg["total_variation_distance"].mean()),
            "marginal_max_tvd": float(marg["total_variation_distance"].max()),
            "marginal_max_abs_z": float(marg["max_abs_z"].max()),
            "joint_mean_abs_difference": float(joint["abs_difference"].mean(skipna=True)),
            "joint_max_abs_difference": float(joint["abs_difference"].max(skipna=True)),
            "spatial_morans_mean_abs_difference": float(
                spat["morans_i_abs_difference"].mean(skipna=True)
            ),
            "spatial_dissimilarity_mean_abs_difference": float(
                spat["dissimilarity_abs_difference"].mean(skipna=True)
            ),
        }
        scores[name] = MethodScore(name, marg, joint, spat, summary)
        rows.append(summary)

    table = pd.DataFrame(rows).set_index("method")

    # Design 5.2 step 2's rule: smaller joint error wins; spatial is the tie-break.
    joint_rank = table["joint_mean_abs_difference"].sort_values()
    best_joint = str(joint_rank.index[0])
    margin = float(joint_rank.iloc[1] - joint_rank.iloc[0]) if len(joint_rank) > 1 else 0.0
    spatial_combined = (
        table["spatial_morans_mean_abs_difference"]
        + table["spatial_dissimilarity_mean_abs_difference"]
    )
    best_spatial = str(spatial_combined.sort_values().index[0])

    # A joint-error gap smaller than this is not a basis for a recommendation:
    # it is below the resolution the between-area statistic can support with 53
    # areas (a rank correlation on n<=53 has a standard error of roughly 1/sqrt(n-1),
    # about 0.14), so the tie-break decides instead.
    resolution = 1.0 / math.sqrt(len(reference["household_size"].by_small_area) - 1)

    if margin >= resolution:
        recommended, basis = best_joint, "smaller joint error (design 5.2 step 2 rule)"
    else:
        recommended, basis = best_spatial, (
            f"joint errors differ by {margin:.3f}, below the {resolution:.3f} "
            f"resolution of a rank correlation on this many areas, so the stated "
            f"tie-break (spatial error) decides"
        )

    recommendation = {
        "recommended_method": recommended,
        "basis": basis,
        "joint_error_ranking": {k: round(float(v), 4) for k, v in joint_rank.items()},
        "joint_error_margin": round(margin, 4),
        "joint_statistic_resolution": round(resolution, 4),
        "spatial_error_ranking": {
            k: round(float(v), 4) for k, v in spatial_combined.sort_values().items()
        },
        "r03_compliance": {k: bool(v) for k, v in table["meets_r03_ranges"].items()},
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
        "claim_boundary": (
            "This compares two scale-down methods against Cobh's own Census "
            "marginals and between-area structure. It is representativeness of a "
            "scale-down, not validation of behaviour, and SAPS publishes no "
            "individual-level joint distribution, so all joint and spatial "
            "statistics are between-small-area quantities."
        ),
    }
    return scores, table, recommendation


# --------------------------------------------------------------------------- #
# R04 acceptance: "every SAPS marginal within the sampling-error band"
# --------------------------------------------------------------------------- #

def marginal_acceptance(
    errors: pd.DataFrame, *, alpha: float = 0.05
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Judge the synthesised marginals against R04's acceptance criterion.

    Design 12, R04: *"Every SAPS marginal within the sampling-error band."*

    **Why this is not "max |z| <= 2".**  The provisional threshold written on
    Day 1 was a flat ``max_abs_z <= 2.0``.  That is a *per-test* critical value
    applied to a *maximum* over many categories, and it is mis-specified: across
    the 90 categories actually tested here (68 age-by-sex, 8 household size, 14
    household type), a **perfect** synthesis - one drawing exactly from Cobh's
    distribution - would still show an expected maximum |z| of about 2.75, and
    would exceed 2.0 in roughly 4 or 5 categories by chance alone.  Judging a
    maximum against a per-test threshold therefore fails a correct synthesis.

    So the band is made simultaneous, by Bonferroni over the number of
    categories actually compared:

        z_crit = Phi^-1( 1 - alpha / (2 * n_categories_total) )

    with ``alpha`` fixed at 0.05.  This is a *specification* of "the
    sampling-error band", not a relaxation of one: the quantity controlled is
    the family-wise error rate, which is what "every marginal within the band"
    means.  Both the corrected verdict and the raw per-test numbers are
    returned, and the E1 report prints both, so the change is visible rather
    than absorbed.

    Two further diagnostics are reported because a single pass/fail hides the
    shape of the error:

    * ``n_exceeding_2`` against ``expected_exceeding_2`` - how many categories
      break the naive threshold, against how many a perfect synthesis would;
    * ``total_variation_distance`` per marginal, which is scale-free and does
      not depend on any critical value at all.
    """
    from scipy.stats import norm

    n_cat = int(errors["n_categories"].sum())
    z_crit = float(norm.ppf(1.0 - alpha / (2.0 * max(n_cat, 1))))
    # Expected maximum of n standard normals (Fisher-Tippett approximation),
    # reported so the reader can see what "perfect" would look like.
    expected_max = float(norm.ppf(1.0 - 1.0 / (2.0 * max(n_cat, 1))))
    per_test_z = float(norm.ppf(1.0 - alpha / 2.0))

    out = errors.copy()
    out["z_crit_simultaneous"] = z_crit
    out["within_simultaneous_band"] = out["max_abs_z"] <= z_crit
    out["within_per_test_band"] = out["max_abs_z"] <= per_test_z

    summary = {
        "criterion": "design 12 R04: every SAPS marginal within the sampling-error band",
        "alpha": alpha,
        "n_categories_total": n_cat,
        "z_crit_per_test": round(per_test_z, 4),
        "z_crit_simultaneous_bonferroni": round(z_crit, 4),
        "expected_max_abs_z_for_a_perfect_synthesis": round(expected_max, 4),
        "observed_max_abs_z": round(float(out["max_abs_z"].max()), 4),
        "marginals_within_simultaneous_band": int(out["within_simultaneous_band"].sum()),
        "marginals_tested": int(len(out)),
        "verdict": "PASS" if bool(out["within_simultaneous_band"].all()) else "FAIL",
        "verdict_under_naive_per_test_threshold": (
            "PASS" if bool(out["within_per_test_band"].all()) else "FAIL"
        ),
        "note": (
            "The per-test verdict is reported for transparency only. A maximum "
            "over many categories cannot be judged against a per-test critical "
            "value; see the docstring."
        ),
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
    }
    return out, summary


# --------------------------------------------------------------------------- #
# Ensemble (generator-bias) acceptance
# --------------------------------------------------------------------------- #

#: Floor on the standard error of an ensemble mean proportion, in households.
#:
#: Half a household is the finest deviation the generator can express at all:
#: the integerisation is column-exact, so a marginal is a vector of whole
#: households and the smallest representable error in any category is half of
#: one, rounded either way. Using it as the floor means the check can never be
#: more sensitive than the quantity it is testing is discrete, and the floor is
#: a property of the generator rather than a tuning knob.
#:
#: The floor matters because two of Baile Nua's marginals - household_size and
#: household type - are reproduced with an across-seed standard deviation of
#: EXACTLY zero. Without a floor their t statistic is 0/0.
ENSEMBLE_SE_FLOOR_HOUSEHOLDS: float = 0.5

#: Below this across-run standard deviation a marginal counts as reproduced
#: deterministically.
#:
#: Not zero, because it is a floating-point computation: ``std(ddof=1)`` over
#: bit-identical proportions returns about 1.7e-16 rather than 0, since the
#: mean it subtracts carries its own rounding. The threshold sits four orders
#: of magnitude above that and four below the smallest real variation measured
#: anywhere in the synthesis (0.0018, the age-band shares), so it cannot
#: mistake one for the other.
ENSEMBLE_DETERMINISTIC_SD_TOLERANCE: float = 1e-12


def ensemble_marginal_acceptance(
    reference_proportions: pd.Series,
    realised_counts: Sequence[pd.Series],
    *,
    alpha: float = 0.05,
    se_floor_households: float = ENSEMBLE_SE_FLOOR_HOUSEHOLDS,
    label: str = "",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Test the ENSEMBLE MEAN of K generator runs against what it must reproduce.

    A different question from :func:`marginal_acceptance`, which is left exactly
    as it was.  That one asks *"could a town of 1,092 households drawn from
    this distribution look like this?"* and judges against multinomial sampling
    error.  This one asks *"is the generator's expected output biased?"* and
    judges against the generator's own measured run-to-run precision.

    **Why both are needed.**  Measured on Baile Nua: the multinomial standard
    error of a 1,092-household draw is about 0.013 in proportion for a category
    near p = 0.25, while the generator's own across-seed standard deviation on
    the same statistic is **0.000000** - it reproduces its control totals
    exactly.  The acceptance band is therefore some twenty-eight times wider
    than the precision of the thing it is testing, and a bias comfortably
    inside it is still an unambiguous defect.  That is not a fault in the band;
    it is the right band for its own question.  It is the wrong band for
    detecting generator bias, which is what design 9.3's "marginals shifted
    10%" control is about.

    The standard error is ``max(sd / sqrt(K), floor)`` and the critical value is
    a **t** quantile on K-1 degrees of freedom, Bonferroni-corrected over the
    categories exactly as the single-realisation band is.  The t rather than
    the normal because the standard deviation is estimated from the same K
    runs, and the floor because a deterministically reproduced marginal has no
    standard deviation to estimate.

    ``reference_proportions`` is what the generator is **contracted** to
    reproduce, and the choice is not cosmetic - see
    :func:`contracted_reference` for why it cannot simply be the raw SAPS
    proportions once the sensitivity exceeds the size of the pipeline's own
    declared transformations.
    """
    if len(realised_counts) < 2:
        raise ValueError(
            f"the ensemble check needs at least 2 runs to estimate a "
            f"run-to-run standard deviation; got {len(realised_counts)}. "
            f"A single run cannot distinguish bias from variability."
        )
    cats = list(reference_proportions.index)
    mat = np.vstack([
        (pd.Series(c).reindex(cats).fillna(0.0).to_numpy(dtype=float))
        for c in realised_counts
    ])
    totals = mat.sum(axis=1)
    if np.any(totals <= 0):
        raise ValueError("a run produced an empty marginal")
    props = mat / totals[:, None]

    k = int(mat.shape[0])
    p_hat = props.mean(axis=0)
    sd = props.std(axis=0, ddof=1)
    n_mean = float(totals.mean())

    floor = float(se_floor_households) / max(n_mean, 1.0)
    se_empirical = sd / math.sqrt(k)
    se = np.maximum(se_empirical, floor)
    floor_binding = se_empirical < floor

    p0 = reference_proportions.reindex(cats).to_numpy(dtype=float)
    p0 = p0 / p0.sum() if p0.sum() > 0 else p0
    z = (p_hat - p0) / se

    t_crit = float(stats.t.ppf(1.0 - alpha / (2.0 * max(len(cats), 1)), k - 1))

    detail = pd.DataFrame(
        {
            "category": cats,
            "reference_proportion": p0,
            "ensemble_mean_proportion": p_hat,
            "across_run_sd": sd,
            "standard_error_used": se,
            "se_floor_was_binding": floor_binding,
            "z": z,
            "abs_z": np.abs(z),
            "within_band": np.abs(z) <= t_crit,
        }
    ).set_index("category")

    observed = float(np.max(np.abs(z)))
    worst = str(detail.abs_z.idxmax())
    summary = {
        "criterion": (
            "the ensemble mean of K generator runs matches what the generator "
            "is contracted to reproduce, at the generator's own measured "
            "run-to-run precision"
        ),
        "label_for": label,
        "k_runs": k,
        "mean_n_per_run": round(n_mean, 1),
        "alpha": alpha,
        "n_categories": len(cats),
        "t_crit_bonferroni": round(t_crit, 4),
        "degrees_of_freedom": k - 1,
        "observed_max_abs_z": round(observed, 4),
        "worst_category": worst,
        "se_floor_households": float(se_floor_households),
        "se_floor_binding_in_n_categories": int(floor_binding.sum()),
        "max_across_run_sd": float(sd.max()),
        "generator_is_deterministic_in_this_marginal": bool(
            sd.max() <= ENSEMBLE_DETERMINISTIC_SD_TOLERANCE
        ),
        "verdict": "PASS" if observed <= t_crit else "FAIL",
        "total_variation_distance": round(
            0.5 * float(np.abs(p_hat - p0).sum()), 6
        ),
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
    }
    return detail, summary


def contracted_reference(
    saps_town_counts: pd.Series,
    scaled_target_counts: pd.Series,
    *,
    key: str = "household_size",
) -> dict[str, Any]:
    """What the generator is contracted to reproduce, and how far that is from SAPS.

    **This is the part of the ensemble check that cannot be waved through.**

    The obvious reference is the raw SAPS proportions, and at the
    single-realisation check's sensitivity that is exactly right. At the
    ensemble check's sensitivity it is not, and the reason is a deliberate
    feature of the pipeline rather than a defect: ``_repair_person_total``
    nudges the household-size mix so that the scaled town satisfies **both** of
    R03's acceptance ranges, which Cobh's real 2.6913 persons per household
    makes jointly unsatisfiable otherwise (I-012, D-010). Measured, that
    deliberate nudge moves the two-person share by -0.0251 and the three-person
    share by +0.0228 - **larger than the 10% shift NC-D2-03 plants**.

    So an ensemble check against raw SAPS rejects a *correct* population, and
    would do so for a declared and necessary reason. That is a false positive,
    and the false-positive control is what forces the design: the ensemble
    tests the generator against the target the declared procedure produces, and
    the deviation of that target from SAPS is reported separately and bounded,
    so it cannot grow unnoticed and cannot hide a bug.

    Two questions, two references, both reported. Collapsing them into one
    number is how a check comes to be either blind or always-firing.
    """
    saps_p = saps_town_counts.astype(float)
    saps_p = saps_p / saps_p.sum()
    tgt_p = scaled_target_counts.astype(float)
    tgt_p = tgt_p / tgt_p.sum()
    cats = list(saps_p.index)
    tgt_p = tgt_p.reindex(cats).fillna(0.0)
    delta = tgt_p - saps_p
    n = float(scaled_target_counts.sum())
    se = np.sqrt(np.clip(saps_p * (1 - saps_p), 1e-12, None) / max(n, 1))
    z = delta / se
    return {
        "key": key,
        "reference_proportions": tgt_p,
        "saps_proportions": saps_p,
        "declared_transformation": (
            "largest-remainder apportionment to the feasible scale factor, "
            "then _repair_person_total to satisfy both R03 ranges (D-010)"
        ),
        "target_vs_saps_max_abs_z": round(float(np.abs(z).max()), 4),
        "target_vs_saps_worst_category": str(np.abs(z).idxmax()),
        "target_vs_saps_tvd": round(0.5 * float(np.abs(delta).sum()), 6),
        "target_vs_saps_delta": {k: round(float(v), 6) for k, v in delta.items()},
        "note": (
            "The ensemble check uses reference_proportions. The deviation of "
            "those from SAPS is this dictionary's own subject, bounded by "
            "ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z and checked separately, so the "
            "declared repair cannot grow into an undeclared bias."
        ),
    }


#: How far the declared scale-down may move a marginal away from SAPS.
#:
#: Set from the measurement, not chosen: the person-total repair currently
#: produces max |z| 2.0712 against SAPS on the household-size marginal, and the
#: single-realisation acceptance band for that marginal is 2.7344. The bound is
#: the band, so the declared transformation is held to the same standard the
#: population itself is - it may use the sampling-error budget, and it may not
#: exceed it. A repair that needed more than that would be changing the
#: distribution rather than reconciling two totals, and should be a decision
#: rather than a side effect.
ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z: float = 2.7344
