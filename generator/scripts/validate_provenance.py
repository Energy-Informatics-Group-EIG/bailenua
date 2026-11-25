#!/usr/bin/env python3
"""Check ``docs/PROVENANCE.md`` against D23 and D24.

Two scripts, not one with a flag: :mod:`gen_provenance` DERIVES provenance
from the code, and this one checks the PAGE ON DISK against the datasets that
record the same facts.  Keeping them apart is the point.  If the validator
imported the generator's model and compared that to D23, it would never read
the published page, and a page that had drifted from the generator - edited by
hand, or generated from an older tree - would pass.  So this script parses the
Markdown it is given and takes nothing about it on trust.  It imports
:mod:`gen_provenance` for one thing only: the declared assumption registries,
to tell a typo from a real flag id.

What is checked
---------------
**D23 — ``run_manifests``.**  Its ``input_sources`` column is
``{source key -> {relpath, sha256, licence, url, ...}}``, the digest recorded
at retrieval time.  Every source the page cites must carry the same SHA-256,
and every source D23 records must be cited somewhere in the page.

**D24 — ``calibration_targets``.**  Each of its targets carries
``source_key`` and ``source_sha256``.  Same two checks, plus the one the
brief asks for: the assumption numbers in the page must match what D24
declares.

Exit status
-----------
``0`` only when the page and both datasets agree on every point.  ``1`` when
they disagree - that is the result, not an error.  ``2`` when a check could
not be run at all (the page is missing, D23 is not on disk, pyarrow absent),
because an unrun check must never read as a pass.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys
from typing import Any

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gen_provenance import CORPUS_REF  # noqa: E402

#: A declared source key: dotted, lower case.  Distinguishes a citation from
#: the module names and licence fragments that also sit in backticks.
_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")

#: ``sources_registry.py`` and ``schema/datasets.yaml`` match :data:`_KEY` and
#: are modules, not sources.  A key never ends in a file extension.
_NOT_A_KEY = (".py", ".json", ".yaml", ".yml", ".md", ".csv", ".xlsx", ".zip")

#: D24 records one target against two tables joined with ``+``: a ratio whose
#: numerator and denominator come from different cubes.  Its ``source_sha256``
#: is not either file's digest, so the parts are checked for citation and the
#: digest comparison is reported as inapplicable rather than as a mismatch.
_D24_COMPOUND = re.compile(r"\s+\+\s+")


def _is_citation(ref: str) -> bool:
    if ref == CORPUS_REF or ref.startswith("sources/"):
        return True
    if ref.endswith(_NOT_A_KEY):
        return False
    return bool(_KEY.match(ref))


# --------------------------------------------------------------------------- #
# the page, as published
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class ParsedPage:
    """``docs/PROVENANCE.md`` read back as data."""

    #: ``dataset_id -> cited refs`` from the main table.
    cited: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    #: ``dataset_id -> ["A-nn", ...]`` from the main table's last column.
    assumptions: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    #: ``ref -> sha256`` from the digest register.  Empty for an UNSOURCED row.
    digests: dict[str, str] = dataclasses.field(default_factory=dict)
    #: Refs the page itself marked UNSOURCED.
    unsourced: list[str] = dataclasses.field(default_factory=list)
    #: True where any dataset cited the whole register.
    cites_whole_register: bool = False
    #: ``ref -> role`` from the "not upstream of any dataset" table, the page's
    #: own published claim about why a declared source is not cited above.
    roles: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def all_cited(self) -> set[str]:
        return {r for refs in self.cited.values() for r in refs}

    @property
    def all_assumptions(self) -> set[str]:
        return {a for ids in self.assumptions.values() for a in ids}


def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def parse_page(text: str) -> ParsedPage:
    page = ParsedPage()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)

        # The main table: five columns, the first carrying **Dnn**.
        head = re.match(r"\*\*(D\d{2}(?:_aggregate)?)\*\*", cells[0])
        if head and len(cells) >= 5:
            dataset_id = head.group(1)
            refs = [
                t for t in re.findall(r"`([^`]+)`", cells[2])
                if _is_citation(t)
            ]
            page.cited[dataset_id] = refs
            if CORPUS_REF in refs:
                page.cites_whole_register = True
            page.assumptions[dataset_id] = sorted(
                set(re.findall(r"\bA-\d+[a-z]?\b", cells[4]))
            )
            continue

        # The digest register: six columns, the first a single backticked ref.
        if len(cells) == 6:
            ref_match = re.fullmatch(r"`([^`]+)`", cells[0])
            if ref_match is None or not _is_citation(ref_match.group(1)):
                continue
            ref = ref_match.group(1)
            sha = re.fullmatch(r"`([0-9a-f]{64})`", cells[4])
            if sha:
                page.digests[ref] = sha.group(1)
            if "UNSOURCED" in cells[1]:
                page.unsourced.append(ref)
            continue

        # The "not upstream of any dataset" table: three columns, the second a
        # single backticked role.
        if len(cells) == 3:
            ref_match = re.fullmatch(r"`([^`]+)`", cells[0])
            role_match = re.fullmatch(r"`([a-z-]+)`", cells[1])
            if ref_match and role_match and _is_citation(ref_match.group(1)):
                page.roles[ref_match.group(1)] = role_match.group(1)
    return page


# --------------------------------------------------------------------------- #
# the datasets
# --------------------------------------------------------------------------- #

def find_d23(run_root: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """D23's part file, looking in ``<root>`` then ``<root>.live``.

    The worktree commits the per-part manifests and gitignores the Parquet, so
    in a worktree the rows live only under the ``.live`` symlink.  Which one
    was read is reported rather than assumed.
    """
    for root in (run_root, run_root.with_name(run_root.name + ".live")):
        parts = sorted((root / "evidence").glob("D23_part*.parquet"))
        if parts:
            return parts[0], str(root)
    return None, ""


def load_d23(path: pathlib.Path) -> dict[str, Any]:
    """``{run_id, sources: {key -> {sha256, relpath}}}`` from the D23 rows."""
    import pyarrow.parquet as pq

    rows = pq.read_table(path).to_pylist()
    if not rows:
        raise ValueError(f"{path} has no rows")
    merged: dict[str, Any] = {}
    run_ids = []
    for row in rows:
        run_ids.append(str(row.get("run_id") or ""))
        doc = json.loads(row.get("input_sources") or "{}")
        for key, entry in (doc.get("sources") or {}).items():
            merged.setdefault(key, entry)
    return {"run_ids": run_ids, "sources": merged, "path": str(path)}


def find_d24(run_root: pathlib.Path) -> pathlib.Path | None:
    for root in (run_root, run_root.with_name(run_root.name + ".live")):
        path = root / "evidence" / "d24_calibration_targets.json"
        if path.is_file():
            return path
    return None


def load_d24(path: pathlib.Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    targets = doc.get("targets") or []
    digests: dict[str, set[str]] = {}
    for target in targets:
        key = str(target.get("source_key") or "")
        sha = str(target.get("source_sha256") or "")
        if key:
            digests.setdefault(key, set()).add(sha)
    blob = json.dumps(doc)
    return {
        "path": str(path),
        "n_targets": len(targets),
        "digests": digests,
        "assumptions": sorted(set(re.findall(r"\bA-\d+[a-z]?\b", blob))),
    }


# --------------------------------------------------------------------------- #
# the checks
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class Finding:
    check: str
    kind: str
    subject: str
    detail: str


def check_d23_digests(page: ParsedPage, d23: dict[str, Any]) -> list[Finding]:
    """Every cited digest must be the one D23 recorded."""
    out: list[Finding] = []
    recorded = d23["sources"]
    for ref in sorted(page.all_cited):
        if ref == CORPUS_REF or ref.startswith("sources/"):
            continue
        entry = recorded.get(ref)
        if entry is None:
            out.append(Finding(
                "D23-DIGEST", "not-recorded", ref,
                "the page cites it; D23's input_sources does not record it, "
                "so the run this D23 describes could not have read it",
            ))
            continue
        page_sha = page.digests.get(ref)
        if not page_sha:
            out.append(Finding(
                "D23-DIGEST", "no-page-digest", ref,
                "cited in the table but absent from the page's digest "
                "register, so there is nothing to compare",
            ))
            continue
        if page_sha != str(entry.get("sha256") or ""):
            out.append(Finding(
                "D23-DIGEST", "mismatch", ref,
                f"page {page_sha[:16]}… vs D23 "
                f"{str(entry.get('sha256'))[:16]}…",
            ))
    return out


def check_d23_coverage(page: ParsedPage, d23: dict[str, Any]) -> list[Finding]:
    """Every source D23 records must be accounted for by the page.

    Accounted for means one of two things, and the page must say which: cited
    upstream of a dataset, or listed in the page's "not upstream of any
    dataset" table with a role.  A ``scoring-only`` role is an answer - the
    model is compared against that source, not built from it - so it closes
    the check.  ``read-but-unattributed`` and ``read-by-nothing`` are not
    answers: they are the page admitting a gap, and the gap is the finding.

    A dataset citing the WHOLE register - D23 does, because
    ``export/run_manifest.py`` iterates it - deliberately does **not** close
    this check.  That citation is a fact about D23's own provenance, and
    letting it stand in for 69 individual answers would make the check
    unfailable, which is the opposite of what it is for.
    """
    out: list[Finding] = []
    for ref in sorted(set(d23["sources"])):
        if ref in page.all_cited:
            continue
        role = page.roles.get(ref)
        if role == "scoring-only":
            continue
        if role is None:
            out.append(Finding(
                "D23-COVERAGE", "unaccounted", ref,
                "D23 records it as a declared input of the run; the page "
                "neither cites it upstream of a dataset nor lists it as not "
                "upstream, so the page is silent about it",
            ))
        else:
            out.append(Finding(
                "D23-COVERAGE", role, ref,
                f"D23 records it as a declared input of the run and the page "
                f"accounts for it as {role!r}, which is a gap and not an "
                f"answer",
            ))
    return out


def check_d24_digests(page: ParsedPage, d24: dict[str, Any]) -> list[Finding]:
    """Every digest D24 recorded for a target must match the page."""
    out: list[Finding] = []
    for ref, shas in sorted(d24["digests"].items()):
        parts = _D24_COMPOUND.split(ref)
        if len(parts) > 1:
            # A ratio target whose numerator and denominator are two cubes.
            # Its recorded digest is neither file's, so only citation is
            # checkable; saying "mismatch" would be wrong.
            unseen = [p for p in parts if p not in page.digests]
            out.append(Finding(
                "D24-DIGEST", "compound-target", ref,
                "D24 records one target against two sources joined with '+', "
                "so its source_sha256 is not either file's digest and no "
                "comparison is possible. "
                + (f"Parts the page does not carry a digest for: "
                   f"{', '.join(unseen)}" if unseen
                   else "Both parts are in the page's digest register."),
            ))
            continue
        page_sha = page.digests.get(ref)
        if page_sha is None:
            role = page.roles.get(ref)
            out.append(Finding(
                "D24-DIGEST", "not-cited", ref,
                f"D24 reads {len(shas)} target(s) from it and the page cites "
                f"it for no dataset"
                + (f"; the page accounts for it as {role!r}" if role else ""),
            ))
            continue
        if len(shas) > 1:
            out.append(Finding(
                "D24-DIGEST", "inconsistent-in-d24", ref,
                f"D24 records {len(shas)} different digests for one source: "
                + ", ".join(sorted(s[:16] + "…" for s in shas)),
            ))
            continue
        d24_sha = next(iter(shas))
        if page_sha != d24_sha:
            out.append(Finding(
                "D24-DIGEST", "mismatch", ref,
                f"page {page_sha[:16]}… vs D24 {d24_sha[:16]}…",
            ))
    return out


def check_d24_assumptions(
    page: ParsedPage, d24: dict[str, Any], declared: set[str],
) -> list[Finding]:
    """The assumption numbers in the page against what D24 declares."""
    out: list[Finding] = []
    in_page = page.all_assumptions
    in_d24 = set(d24["assumptions"])

    if not in_d24:
        out.append(Finding(
            "D24-ASSUMPTIONS", "d24-declares-none", "D24",
            f"the page carries {len(in_page)} assumption numbers and D24 "
            f"declares none: its {d24['n_targets']} targets have no "
            f"assumption field at all. The schema's D24 does not declare one "
            f"either - its seventeen fields are target, source and tolerance "
            f"columns - so the assumption cross-check the brief asks for "
            f"cannot be satisfied from D24 as it stands. This is a "
            f"disagreement between the page and the dataset and is reported "
            f"as one; the registries the page actually rests on are "
            f"validation.assumption_sweep.ASSUMPTION_FLAGS and "
            f"export.tariffs.TARIFF_ASSUMPTIONS",
        ))
    else:
        for flag_id in sorted(in_page - in_d24):
            out.append(Finding(
                "D24-ASSUMPTIONS", "in-page-not-in-d24", flag_id,
                "the page depends on it and D24 does not declare it",
            ))
        for flag_id in sorted(in_d24 - in_page):
            out.append(Finding(
                "D24-ASSUMPTIONS", "in-d24-not-in-page", flag_id,
                "D24 declares it and no dataset in the page depends on it",
            ))

    for flag_id in sorted(in_page - declared):
        out.append(Finding(
            "D24-ASSUMPTIONS", "undeclared-flag", flag_id,
            "the page names it and neither declared registry has it: a typo "
            "or a flag that has been removed",
        ))
    return out


def check_unsourced_declared(page: ParsedPage) -> list[Finding]:
    """A page-declared UNSOURCED is a finding in its own right."""
    return [
        Finding(
            "UNSOURCED", "unsourced", ref,
            "cited by at least one dataset and does not resolve to a file "
            "under sources/ with a manifest beside it",
        )
        for ref in sorted(page.unsourced)
    ]


def declared_flag_ids() -> set[str]:
    from baile_nua.export.tariffs import TARIFF_ASSUMPTIONS
    from baile_nua.validation.assumption_sweep import ASSUMPTION_FLAGS

    return {f.flag_id for f in (*ASSUMPTION_FLAGS, *TARIFF_ASSUMPTIONS)}


# --------------------------------------------------------------------------- #

def validate(
    page_path: pathlib.Path, run_root: pathlib.Path,
) -> tuple[int, dict[str, Any]]:
    report: dict[str, Any] = {
        "page": str(page_path), "run_root": str(run_root),
        "checks": {}, "findings": [], "unrun": [],
    }
    if not page_path.is_file():
        report["unrun"].append(f"{page_path} does not exist; run gen_provenance.py")
        return 2, report

    page = parse_page(page_path.read_text(encoding="utf-8"))
    report["page_summary"] = {
        "datasets": len(page.cited),
        "distinct_sources_cited": len(page.all_cited),
        "distinct_assumptions": len(page.all_assumptions),
        "digests_published": len(page.digests),
        "unsourced": sorted(page.unsourced),
        "cites_whole_register": page.cites_whole_register,
    }
    if not page.cited:
        report["unrun"].append(
            "no dataset rows parsed out of the page: the table's shape has "
            "changed and every check below would have passed on nothing"
        )
        return 2, report

    findings: list[Finding] = []
    findings += check_unsourced_declared(page)

    d23_path, d23_root = find_d23(run_root)
    if d23_path is None:
        report["unrun"].append(
            f"no D23_part*.parquet under {run_root}/evidence or "
            f"{run_root}.live/evidence: the digest check cannot be run"
        )
    else:
        try:
            d23 = load_d23(d23_path)
        except ImportError as exc:
            report["unrun"].append(f"D23 needs pyarrow: {exc}")
        except Exception as exc:                     # reported, not swallowed
            report["unrun"].append(f"D23 at {d23_path} unreadable: {exc}")
        else:
            report["checks"]["D23"] = {
                "read_from": d23["path"], "root": d23_root,
                "run_ids": d23["run_ids"], "n_sources": len(d23["sources"]),
            }
            findings += check_d23_digests(page, d23)
            findings += check_d23_coverage(page, d23)

    d24_path = find_d24(run_root)
    if d24_path is None:
        report["unrun"].append(
            f"no d24_calibration_targets.json under {run_root}/evidence: the "
            f"assumption and target checks cannot be run"
        )
    else:
        d24 = load_d24(d24_path)
        report["checks"]["D24"] = {
            "read_from": d24["path"], "n_targets": d24["n_targets"],
            "n_sources": len(d24["digests"]),
            "assumptions_declared": d24["assumptions"],
        }
        findings += check_d24_digests(page, d24)
        findings += check_d24_assumptions(page, d24, declared_flag_ids())

    report["findings"] = [dataclasses.asdict(f) for f in findings]
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.check] = counts.get(f.check, 0) + 1
    report["n_findings"] = len(findings)
    report["findings_by_check"] = counts

    if report["unrun"]:
        return 2, report
    return (1 if findings else 0), report


def _print(report: dict[str, Any]) -> None:
    print(f"page     : {report['page']}")
    for name, info in report.get("checks", {}).items():
        print(f"{name:9s}: {info.get('read_from')}")
        if name == "D23":
            print(f"           {info['n_sources']} declared input sources; "
                  f"run_ids {info['run_ids']}")
        if name == "D24":
            print(f"           {info['n_targets']} targets over "
                  f"{info['n_sources']} sources; assumption ids declared: "
                  f"{info['assumptions_declared'] or 'none'}")
    summary = report.get("page_summary")
    if summary:
        print(
            f"parsed   : {summary['datasets']} datasets, "
            f"{summary['distinct_sources_cited']} distinct sources, "
            f"{summary['distinct_assumptions']} assumptions, "
            f"{summary['digests_published']} digests"
        )
    for line in report.get("unrun", []):
        print(f"UNRUN    : {line}")
    for finding in report.get("findings", []):
        print(
            f"{finding['check']:17s} {finding['kind']:22s} "
            f"{finding['subject']}\n                  {finding['detail']}"
        )
    print(
        f"\n{report.get('n_findings', 0)} finding(s) "
        f"{report.get('findings_by_check', {})}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--page", default=str(PROJECT_ROOT / "docs" / "PROVENANCE.md"))
    ap.add_argument(
        "--run-root", default=str(PROJECT_ROOT / "v1"),
        help="package to read D23 and D24 from (default: v1; <root>.live is "
             "tried too, because a worktree gitignores the Parquet)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, report = validate(
        pathlib.Path(args.page), pathlib.Path(args.run_root))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print(report)
        print(
            "RESULT: " + {
                0: "the page and D23/D24 agree",
                1: "the page and D23/D24 DISAGREE",
                2: "a check could not be run",
            }[code]
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
