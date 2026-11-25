"""Source acquisition and the source-use register (brief; design 7.1, D24).

Two rules from the brief are enforced here mechanically rather than by habit:

> Record every download in sources/SOURCES.md before using it.

> Do not hard-code statistics from memory. Every calibration number traces to a
> file in sources/.

So: :func:`fetch` writes a per-file manifest (URL, retrieval date, licence,
SHA-256, intended use, model-development exposure) **at download time**, and
:func:`require` refuses to hand a path to the rest of the system unless that
manifest exists.  A file that appeared in ``sources/`` by some other route
cannot be used by accident.

``SOURCES.md`` is regenerated from the manifests by :func:`write_register`, so
the register cannot drift from what is actually on disk.
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any, Literal

from baile_nua.hashing import hash_file

__all__ = [
    "Source",
    "SOURCES_DIR",
    "fetch",
    "require",
    "manifest_for",
    "all_manifests",
    "write_register",
    "SourceError",
    "REGISTRY",
    "register",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = PROJECT_ROOT / "sources"

IntendedUse = Literal["calibration", "validation", "reference"]
Exposure = Literal["none", "design", "selection", "tuning"]


class SourceError(RuntimeError):
    """A source was used without being registered, or its bytes have changed."""


@dataclasses.dataclass(frozen=True)
class Source:
    """A declared public input.  Declared once, in :data:`REGISTRY`."""

    key: str
    url: str
    relpath: str                 # under sources/
    licence: str
    publisher: str
    title: str
    intended_use: IntendedUse
    #: 7.1: did it influence design, model selection or tuning?
    model_development_exposure: Exposure = "none"
    #: Which design requirement or section needs it.
    used_for: str = ""
    #: Set when the design's preferred source was unreachable (brief: flag [A]).
    substitute_flag: str | None = None
    encoding: str = "utf-8"
    #: For a public dataset whose only access mechanism is an HTML form POST.
    #:
    #: SEAI's National BER Research Tool is CC-BY 4.0 open data listed on
    #: data.gov.ie, and its download is an ASP.NET postback: the page carries
    #: __VIEWSTATE and __EVENTVALIDATION tokens that must be echoed back with
    #: the submit button's name. A plain GET returns the search page, not the
    #: data. So the fetcher GETs the URL, lifts the named hidden fields, and
    #: POSTs them with the extra fields below.
    #:
    #: ``{"hidden": ("__VIEWSTATE", ...), "fields": {"<button name>": "<value>"}}``
    #:
    #: Declared on the source rather than scripted ad hoc, so the access
    #: mechanism travels with the declaration and the manifest still records
    #: the bytes that arrived.
    form_post: dict[str, Any] | None = None

    @property
    def path(self) -> Path:
        return SOURCES_DIR / self.relpath

    @property
    def manifest_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".manifest.json")


#: Every public source this build uses.  Nothing is downloaded that is not here,
#: and CER/ISSDA and other licensed sources are deliberately absent (brief).
REGISTRY: dict[str, Source] = {}


def register(src: Source) -> Source:
    if src.key in REGISTRY:
        raise ValueError(f"duplicate source key {src.key!r}")
    REGISTRY[src.key] = src
    return src


# --------------------------------------------------------------------------- #

def manifest_for(src: Source) -> dict[str, Any] | None:
    p = src.manifest_path
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _write_manifest(src: Source, *, http_status: int | None) -> dict[str, Any]:
    sha = hash_file(src.path)
    doc = {
        "key": src.key,
        "title": src.title,
        "publisher": src.publisher,
        "url": src.url,
        "relpath": src.relpath,
        "retrieved_at": time.strftime("%Y-%m-%d", time.gmtime()),
        "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "http_status": http_status,
        "bytes": src.path.stat().st_size,
        "sha256": sha,
        "licence": src.licence,
        "intended_use": src.intended_use,
        "model_development_exposure": src.model_development_exposure,
        "used_for": src.used_for,
        "substitute_flag": src.substitute_flag,
        "encoding": src.encoding,
        "note": (
            "Raw input, read-only after download. Excluded from git; this "
            "manifest is committed in its place."
        ),
    }
    src.manifest_path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return doc


def _fetch_via_form_post(src: Source, *, headers: dict[str, str], timeout: int):
    """GET the page for its hidden tokens, then POST the download button.

    Raises rather than returning the search page: a 200 that is HTML instead
    of the dataset would otherwise be hashed and recorded as a successful
    download of a web page.
    """
    import re

    import requests

    spec = src.form_post or {}
    session = requests.Session()
    session.headers.update(headers)
    page = session.get(src.url, timeout=timeout)
    page.raise_for_status()
    data: dict[str, str] = {}
    for name in spec.get("hidden", ()):
        m = re.search(rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', page.text)
        if m is None:
            raise SourceError(
                f"{src.key}: the page at {src.url} no longer carries the "
                f"hidden field {name!r}, so the form POST cannot be built. "
                f"The site's download mechanism has changed."
            )
        data[name] = m.group(1)
    data.update(spec.get("fields", {}))
    resp = session.post(src.url, data=data, timeout=timeout, stream=True,
                        allow_redirects=True)
    ctype = resp.headers.get("Content-Type", "")
    disposition = resp.headers.get("Content-Disposition", "")
    if "html" in ctype.lower() and "attachment" not in disposition.lower():
        raise SourceError(
            f"{src.key}: the POST to {src.url} returned HTML "
            f"({ctype}), not a file. That is the search page, which means the "
            f"form fields are stale - recording it would hash a web page as "
            f"the dataset."
        )
    return resp


def fetch(src: Source, *, timeout: int = 600, force: bool = False) -> dict[str, Any]:
    """Download a declared source and record it, in that order.

    Idempotent: if the file is already present with a matching manifest, the
    bytes are re-hashed and the download is skipped.  That re-hash is the point
    - ``sources/`` is read-only after download, and a changed hash means
    something edited a raw input, which must be loud.
    """
    import requests

    existing = manifest_for(src)
    if existing and src.path.is_file() and not force:
        actual = hash_file(src.path)
        if actual != existing["sha256"]:
            raise SourceError(
                f"{src.relpath} has changed on disk since it was registered "
                f"(manifest {existing['sha256'][:16]}..., actual {actual[:16]}...). "
                f"sources/ is read-only after download. Investigate before using it."
            )
        # The bytes match, but the DECLARATION may have moved on. The manifest
        # is what SOURCES.md is generated from, so a changed exposure or use
        # that is not written through leaves the published register saying the
        # old thing - and exposure is exactly the field a reader consults to
        # know whether a source may validate what it calibrated (7.1). That
        # happened: seai.ber.research_tool was re-declared tuning-exposed for
        # fabric and the register still read "none".
        drifted = {
            field: (existing.get(field), getattr(src, field))
            for field in ("intended_use", "model_development_exposure",
                          "used_for", "licence", "title", "publisher",
                          "substitute_flag")
            if existing.get(field) != getattr(src, field)
        }
        if drifted:
            refreshed = _write_manifest(
                src, http_status=existing.get("http_status")
            )
            refreshed["declaration_refreshed"] = {
                k: {"was": v[0], "now": v[1]} for k, v in drifted.items()
            }
            return refreshed
        return existing

    src.path.parent.mkdir(parents=True, exist_ok=True)
    # An identifying User-Agent, as public statistical APIs ask for. The CSO
    # PxStat endpoint returns 403 to the bare `requests` default on some
    # datasets, so this is required rather than merely polite.
    headers = {
        "User-Agent": (
            "baile-nua/0.1 (HRSD_Occupants research build; "
            "contact: brianoregan78@gmail.com)"
        ),
        "Accept": "*/*",
    }
    if src.form_post:
        resp = _fetch_via_form_post(src, headers=headers, timeout=timeout)
    else:
        resp = requests.get(src.url, timeout=timeout, stream=True,
                            headers=headers)
    resp.raise_for_status()
    tmp = src.path.with_suffix(src.path.suffix + ".part")
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    tmp.replace(src.path)
    return _write_manifest(src, http_status=resp.status_code)


def require(key: str) -> Path:
    """Return a source's path, refusing if it was never registered or has drifted.

    This is the only sanctioned way for the generator to open a raw input.
    """
    try:
        src = REGISTRY[key]
    except KeyError:
        raise SourceError(
            f"source {key!r} is not declared in baile_nua.sources.REGISTRY. "
            f"Declare it (with URL, licence, intended use and exposure) before use; "
            f"the brief requires every download to be recorded before it is used."
        ) from None
    man = manifest_for(src)
    if man is None:
        raise SourceError(
            f"source {key!r} has no manifest at {src.manifest_path}. "
            f"Run `baile-nua sources fetch` first: a source must be recorded in the "
            f"register before it is used."
        )
    if not src.path.is_file():
        raise SourceError(f"source {key!r} is registered but missing from disk: {src.path}")
    actual = hash_file(src.path)
    if actual != man["sha256"]:
        raise SourceError(
            f"source {key!r} bytes changed since download "
            f"(manifest {man['sha256'][:16]}..., actual {actual[:16]}...)."
        )
    return src.path


def all_manifests() -> list[dict[str, Any]]:
    out = []
    for src in REGISTRY.values():
        man = manifest_for(src)
        if man is not None:
            out.append(man)
    return sorted(out, key=lambda m: m["key"])


# --------------------------------------------------------------------------- #

_REGISTER_HEADER = """# Source-use register

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

Generated from the per-file manifests under `sources/` by
`baile_nua.sources.write_register`. Do not edit by hand: edit the source
declarations in `scripts/baile_nua/sources_registry.py` and re-run
`baile-nua sources register`.

Every input is recorded here **before** it is used, per the brief and design
7.1. Design 7.1, binding:

> A source-use register records each dataset's use per household, site, time
> period, geography and model-development exposure (whether it influenced design
> choices, model selection or tuning). Calibration and validation may share a
> corpus only if the validation units are disjoint on the dimension relevant to
> the claim, and never if they influenced model selection or tuning. **Any
> validation result that touched tuning-exposed data is a blocking failure.**

## Rules applied in this run

1. **Public data only.** CSO Census 2022 SAPS, CSO vital statistics, SEAI BER
   public data, Met Éireann historical data, Eurostat HETUS tables, and open
   appliance datasets.
2. **CER/ISSDA and any licensed or restricted source is NOT used.** No row below
   carries a restricted licence, and E1 depends on no data-access application.
3. **No calibration number is hard-coded from memory.** Every number the
   generator uses traces through D24 `calibration_targets` to a file below and
   its SHA-256.
4. **Raw files are read-only after download.** `baile_nua.sources.require`
   re-hashes a file on every use and refuses it if the bytes have changed.
5. A source that was unreachable is logged in `docs/ISSUES.md` and replaced by
   the next-best public source, flagged `[A]` in the Substitute column.

## Intended use

| Value | Meaning |
| --- | --- |
| `calibration` | Allowed to shape parameters (design 7.1 calibration sources) |
| `validation` | Never used for calibration; splits fixed and hashed in D24 before comparison |
| `reference` | Structural or documentary reference; shapes no parameter |

## Model-development exposure (design 7.1)

| Value | Meaning |
| --- | --- |
| `none` | Has not influenced design, model selection or tuning |
| `design` | Influenced a design choice |
| `selection` | Influenced model selection |
| `tuning` | Influenced tuning. **Blocks any validation claim using it.** |
"""


def write_register(path: Path | None = None) -> Path:
    p = Path(path) if path else SOURCES_DIR / "SOURCES.md"
    mans = all_manifests()
    lines = [_REGISTER_HEADER, "", "## Register", ""]
    if not mans:
        lines.append("*No sources downloaded yet.*")
    else:
        lines += [
            "| Key | Title | Publisher | Retrieved | Licence | Bytes | SHA-256 | Use | Exposure | Substitute | Used for |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for m in mans:
            lines.append(
                f"| `{m['key']}` | {m['title']} | {m['publisher']} | {m['retrieved_at']} | "
                f"{m['licence']} | {m['bytes']:,} | `{m['sha256'][:16]}…` | {m['intended_use']} | "
                f"{m['model_development_exposure']} | {m['substitute_flag'] or '—'} | {m['used_for']} |"
            )
        lines += ["", "Full SHA-256 digests are in each file's `.manifest.json`, which is committed.", ""]

    declared_not_fetched = sorted(set(REGISTRY) - {m["key"] for m in mans})
    if declared_not_fetched:
        lines += [
            "## Declared but not retrieved",
            "",
            "Logged in `docs/ISSUES.md` where the failure was not simply that the "
            "source is not needed by E1.",
            "",
            "| Key | Title | URL |",
            "| --- | --- | --- |",
        ]
        for k in declared_not_fetched:
            s = REGISTRY[k]
            lines.append(f"| `{k}` | {s.title} | {s.url} |")
        lines.append("")

    lines += [
        "## Sources deliberately NOT used",
        "",
        "| Source | Reason |",
        "| --- | --- |",
        "| CER Smart Metering trial (ISSDA) | Licensed/restricted. The brief forbids it. Design 7.1 lists it as a **validation** source, so its absence does not affect E1, which makes no V2/V3/V4 claim. |",
        "| CSO POWSCAR commuting microdata | Restricted microdata (U04/5.2 step 4). E1 uses the public SAPS travel-to-work marginals instead, flagged `[A]`. |",
        "| Irish time-use diary microdata | Does not exist in accessible form (E0-2 / U04 / risk K02). Eurostat HETUS public aggregates used instead; the activity engine is flagged **VERIFIED, NOT CALIBRATED**. |",
        "| IDEAL (UK) | Not required by E1; licence to be confirmed in WP1 (U05). |",
        "",
        "## Non-data sources (code and documents consulted, not ingested)",
        "",
        "| # | Source | Path | Retrieved | Role |",
        "| --- | --- | --- | --- | --- |",
        "| C1 | Baile Nua Technical Design Review, revision 3 | `docs/Baile_Nua_Technical_Design_Review_r3.md` | 2026-10-08 | Binding design. Architecture frozen. |",
        "| C2 | MIMIC working tree | `/Users/brianoregan/Documents/GitHub/mimic` | 2026-10-08 | Trait names, value sets, schema 1.1, the public API contract. Read only; never modified (ISSUES.md I-001 to I-003). |",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
