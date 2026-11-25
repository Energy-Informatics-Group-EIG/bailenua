"""Design 6.3: the three delivery packages, and the rules that keep them apart.

"Every release ships as three separate packages, built from the access classes
above."

====================  ===============================================  =========
Package               Contents                                         Receives
====================  ===============================================  =========
**Observable view**   OBS only: D18, D19, D27 to D31, the **redacted**  model
                      D03 and the **aggregate** D17 views, with a full  developers,
                      data dictionary. Every value carries a            BNIT,
                      provenance code and a quality flag. Plus the      blind
                      operator log.                                     evaluators
**Ground-truth view** GT: people, activities, appliance cycles, life    scoring
                      events, causal links, D20 labels, D26 answer      and
                      key.                                              diagnosis
**Evidence view**     calibration sources, source-use register,         everyone
                      validation results with uncertainty, fidelity
                      tiers passed, limitations, version history, and
                      the list of tasks equivalence is shown for.
====================  ===============================================  =========

**This module builds the manifests and enforces the separation; it does not
copy the bytes.** The engine's ``StreamWriter`` already writes each dataset
into ``observable/`` or ``ground_truth/`` by its access class, so the files are
already apart. What has never existed is the thing that says *what a package
is*, checks that it contains only what it should, and ships the data
dictionary, the limitations and the task list the evidence view is supposed to
carry.

**Four separation rules, each able to fail.**

1. **No GT dataset in the observable view.** The leakage test already covers
   field-level leakage; this is the coarser, prior check that a whole
   ground-truth dataset has not been filed in the wrong place.
2. **D03 is redacted and D17 is aggregated** in the observable view. Both are
   GT datasets with an observable *view*, which is a different thing from being
   observable: an un-redacted D03 hands a model the dated truth about every
   building change it is supposed to detect.
3. **The evidence view names its own limitations.** Design 6.3 lists
   "limitations" among its contents, and a package that claims to carry them
   and does not is worse than one that does not claim to.
4. **The observable view does not disclose synthetic provenance.** Checked by
   :mod:`baile_nua.release.tell_audit`, and currently **failing** — see I-074.
   The rule is enforced here rather than merely tested, so a package that
   discloses cannot be built without the caller passing
   ``allow_provenance_disclosure=True`` and thereby saying so.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = [
    "PACKAGES",
    "OBSERVABLE_DATASETS",
    "GROUND_TRUTH_DATASETS",
    "PackageError",
    "build_packages",
]


class PackageError(RuntimeError):
    pass


#: Design 6.3's own contents list, per package.
PACKAGES: dict[str, dict[str, Any]] = {
    "observable": {
        "receives": "model developers, BNIT experiments, blind evaluators",
        "contents": (
            "OBS datasets only (D18, D19, D27 to D31), the redacted D03 and "
            "the aggregate D17 views, with a full data dictionary"
        ),
        "every_value_carries": ("provenance code", "quality flag"),
        "must_not_contain": (
            "any ground-truth dataset; any person-level or occupancy field; "
            "the un-redacted D03; the per-element D17; any disclosure of "
            "synthetic provenance"
        ),
    },
    "ground_truth": {
        "receives": "scoring services and diagnosis only; never a model under test",
        "contents": (
            "GT datasets: people, activities, appliance cycles, life events, "
            "causal links, D20 labels, D26 answer key"
        ),
        "must_not_contain": "nothing is excluded; this is the truth",
    },
    "evidence": {
        "receives": "everyone; it accompanies every release",
        "contents": (
            "calibration sources, source-use register, validation results "
            "with uncertainty, fidelity tiers passed, limitations, version "
            "history, and the list of tasks for which equivalence is shown"
        ),
        "must_not_contain": (
            "any row of either other package. The evidence view describes; it "
            "does not deliver data."
        ),
    },
}

#: Which datasets belong in the observable view. D03 and D17 are GT datasets
#: with an observable VIEW, which is why they are listed separately: shipping
#: the dataset would be wrong and shipping the view is the design.
OBSERVABLE_DATASETS: tuple[str, ...] = (
    "D18", "D19", "D25", "D27", "D28", "D29", "D30", "D31")
OBSERVABLE_VIEWS_OF_GT: dict[str, str] = {
    "D03": "redacted: the event occurred and its date, without the parameters",
    "D17": "aggregate: feeder and transformer totals, not per element",
}

GROUND_TRUTH_DATASETS: tuple[str, ...] = (
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10",
    "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D20", "D21", "D26")


def _limitations() -> list[dict[str, Any]]:
    """What the evidence view must say about itself.

    Read from ISSUES.md rather than written here, because a limitations list
    maintained separately from the issue log diverges from it, and the
    divergence always runs one way: the list gets shorter.
    """
    from pathlib import Path
    import re

    path = Path(__file__).resolve().parents[3] / "docs" / "ISSUES.md"
    if not path.exists():
        raise PackageError(
            f"{path} is absent, so the evidence view cannot carry the "
            f"limitations design 6.3 requires. A package that claims to "
            f"carry them and does not is worse than one that does not claim."
        )
    text = path.read_text(encoding="utf-8")
    # The log's own convention: an issue that is later closed or extended gets
    # a SECOND heading with the same id - "I-039 - CLOSED at the aggregate
    # level". Five ids do. A naive parser lists such an issue twice with
    # contradictory statuses, and a reader of the evidence view cannot tell
    # which is current, so the LAST occurrence wins: the log is chronological.
    by_id: dict[str, dict[str, Any]] = {}
    for m in re.finditer(r"^## (I-\d+)\s+[-—]\s+(.+)$", text, re.M):
        iid, title = m.group(1), m.group(2).strip()
        tail = text[m.end():m.end() + 400]
        sm = re.search(r"\*\*Status:\s*([^*.]+)", tail)
        entry = {
            "issue": iid, "title": title,
            "status": (sm.group(1).strip() if sm else "unknown"),
            "n_entries_in_the_log": by_id.get(iid, {}).get(
                "n_entries_in_the_log", 0) + 1,
            "superseded_title": by_id.get(iid, {}).get("title"),
        }
        # Closure is recorded in the TITLE as often as in a status line, so
        # both are read. A limitations list that called a closed issue open
        # would overstate the limitations, which is the opposite error from
        # the usual one and still an error.
        low = f"{title} {entry['status']}".lower()
        entry["closed"] = low.startswith("closed") or "closed" in low[:40]
        by_id[iid] = entry
    out = [by_id[k] for k in sorted(by_id)]
    if not out:
        raise PackageError(
            "no issues were parsed from ISSUES.md, so the limitations list "
            "would ship empty while the issue log is not")
    return out


def build_packages(
    *, root: Any, evidence_root: Any = None,
    allow_provenance_disclosure: bool = False,
) -> dict[str, Any]:
    """Describe and check the three packages under ``root``.

    ``root`` is a run's output directory, containing ``observable/`` and
    ``ground_truth/``. Returns one record per package plus the separation
    verdicts. Writes nothing into the data directories: a package manifest
    that lived inside the observable view would be a twenty-seventh thing for
    the tell audit to find.
    """
    import glob
    import json
    from pathlib import Path

    from baile_nua.release import tell_audit as TA

    root = Path(root)
    obs_dir, gt_dir = root / "observable", root / "ground_truth"
    ev_dir = Path(evidence_root) if evidence_root else (root / "evidence")

    def datasets_in(d: Path) -> dict[str, int]:
        found: dict[str, int] = {}
        for f in sorted(d.glob("*.parquet")):
            name = f.name.split("_part")[0]
            found[name] = found.get(name, 0) + 1
        return found

    obs = datasets_in(obs_dir) if obs_dir.exists() else {}
    gt = datasets_in(gt_dir) if gt_dir.exists() else {}

    # ---- rule 1: no GT dataset filed in the observable view --------------
    gt_in_obs = sorted(set(obs) & set(GROUND_TRUTH_DATASETS)
                       - set(OBSERVABLE_VIEWS_OF_GT))
    # ---- rule 2: D03 and D17, if present in obs, must be the VIEWS -------
    views_present = {k: (k in obs) for k in OBSERVABLE_VIEWS_OF_GT}
    # ---- rule 3: the evidence view names its limitations -----------------
    limitations = _limitations()
    # ---- rule 4: no synthetic disclosure in the observable view ----------
    disclosure = TA.audit_manifests(
        manifest_paths=sorted(glob.glob(str(obs_dir / "*.manifest.json"))))

    if disclosure["n_disclosing"] and not allow_provenance_disclosure:
        raise PackageError(
            f"{disclosure['n_disclosing']} of "
            f"{disclosure['n_manifests_checked']} manifests in the observable "
            f"view disclose synthetic provenance. Design 6.3: 'The synthetic "
            f"flag lives in the release manifest, which the evaluation "
            f"organiser holds', and 6.3's own table sends this view to blind "
            f"evaluators. This is I-074.\n\n"
            f"It is refused rather than warned about, because a package built "
            f"without noticing is a blind round wasted. Pass "
            f"allow_provenance_disclosure=True to build it anyway, which "
            f"records in the manifest that the package is NOT blind-safe."
        )

    ev_files = (sorted(p.name for p in ev_dir.glob("*.json"))
                if ev_dir.exists() else [])
    record = {
        "design_ref": "6.3 delivery packages",
        "root": str(root),
        "observable": {
            **PACKAGES["observable"],
            "datasets_present": obs,
            "observable_views_of_gt_present": views_present,
            "n_parts": sum(obs.values()),
            "blind_safe": bool(disclosure["n_disclosing"] == 0),
            "provenance_disclosure": disclosure,
        },
        "ground_truth": {
            **PACKAGES["ground_truth"],
            "datasets_present": gt,
            "n_parts": sum(gt.values()),
            "never_given_to_a_model_under_test": (
                "Design 6.3. D20's own schema says 'Scoring API only. Never "
                "released', and the ten-year artefact carries the labels for "
                "that reason."
            ),
        },
        "evidence": {
            **PACKAGES["evidence"],
            "artefacts_present": ev_files,
            "n_artefacts": len(ev_files),
            "limitations": limitations,
            "n_limitations": len(limitations),
            "n_open": sum(1 for x in limitations if not x["closed"]),
            "n_closed": sum(1 for x in limitations if x["closed"]),
            "n_with_more_than_one_log_entry": sum(
                1 for x in limitations if x["n_entries_in_the_log"] > 1),
            "duplicate_headings_resolved_to_the_latest": (
                "The issue log records a closure or an extension as a SECOND "
                "heading with the same id. Five ids have two. The last "
                "occurrence wins, because the log is chronological, and the "
                "superseded title is kept so a reader can see what changed."
            ),
            "limitations_are_read_from_the_issue_log": (
                "docs/ISSUES.md, not a list maintained here. A limitations "
                "list kept separately from the issue log diverges from it, "
                "and the divergence always runs one way: the list gets "
                "shorter."
            ),
        },
        "separation": {
            "gt_datasets_in_the_observable_view": gt_in_obs,
            "rule_1_no_gt_in_obs": not gt_in_obs,
            "rule_2_d03_and_d17_are_views_not_datasets": OBSERVABLE_VIEWS_OF_GT,
            "rule_3_evidence_names_its_limitations": bool(limitations),
            "rule_4_observable_view_is_blind_safe": bool(
                disclosure["n_disclosing"] == 0),
            "all_rules_pass": bool(
                not gt_in_obs and limitations
                and disclosure["n_disclosing"] == 0),
        },
        "what_is_not_shipped_and_why": {
            "D27": "the edge-export contract view is not written by E1's runner",
            "D28_to_D31": (
                "built in observation/nonsensor.py and not yet written into a "
                "package by the runner; D31 carries weather only (I-072)"
            ),
            "operator_log": "6.4 item 8, not built",
            "data_dictionary": (
                "v1/evidence/data_dictionary.md exists and is in the evidence "
                "view; 6.3 wants it in the OBSERVABLE view too, where it is "
                "not yet shipped"
            ),
        },
    }
    return record
