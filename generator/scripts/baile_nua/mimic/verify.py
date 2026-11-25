"""MIMIC-side verification: database integrity, dashboard, purge (design 5.14 T1/T9).

All queries go through the running container's MySQL client rather than a Python
driver, so no extra dependency is needed and the checks run against exactly the
database MIMIC itself is using.

The integrity checks are the ones T1 means by "0 integrity errors": every
foreign key resolves, every session has the length MIMIC's own config declares,
every response's recorded signal matches the permutation it was chosen from, and
no forbidden column exists on any profile table.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import requests

__all__ = [
    "mysql_query",
    "db_integrity",
    "grand_mean_pi_from_db",
    "fetch_dashboard",
    "fetch_dashboard_with_transport",
    "CLI_V2_SKIPPED",
    "purge_synthetic",
    "RESEARCHER_TOKEN",
    "MYSQL_CONTAINER",
]

MYSQL_CONTAINER = "bailenua-mimic-local-mysql-1"
#: Set by ``provision`` in the sandbox's ``config/local.php``.
RESEARCHER_TOKEN = "bailenua-local-sandbox-token"


def mysql_query(sql: str, *, container: str = MYSQL_CONTAINER) -> list[list[str]]:
    """Run one query, returning tab-separated rows.  Raises on a MySQL error."""
    # ``--default-character-set=utf8mb4`` is not optional. The client in the
    # container defaults to latin1, so MIMIC's own age bands - which use an
    # EN-DASH, U+2013, and are the source of defect I-003 - came back as the
    # single byte 0x96 and `subprocess` raised UnicodeDecodeError on the first
    # row of a profile SELECT. Every previous caller here ran COUNT queries, so
    # the only reason this had never been seen is that nothing had yet read a
    # text column out of MIMIC.
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "mysql", "-umimic", "-pmimic",
         "--default-character-set=utf8mb4", "-N", "-B", "mimic", "-e", sql],
        capture_output=True, text=True, timeout=1800,
    )
    err = "\n".join(
        l for l in proc.stderr.splitlines()
        if l.strip() and "Using a password" not in l
    )
    if proc.returncode != 0 or err:
        raise RuntimeError(f"MySQL error for {sql[:120]!r}: {err or proc.returncode}")
    return [line.split("\t") for line in proc.stdout.splitlines() if line.strip()]


def _scalar(sql: str) -> int:
    rows = mysql_query(sql)
    return int(rows[0][0]) if rows and rows[0] and rows[0][0] not in ("NULL", "") else 0


def db_integrity(*, session_length: int = 13) -> dict[str, Any]:
    """Every integrity check T1 requires, each counted separately.

    Separately, not totalled with a single "ok" flag, so that a failure says
    which invariant broke.
    """
    checks: dict[str, int] = {}

    # -- referential integrity ------------------------------------------------
    checks["profiles_without_participant"] = _scalar(
        "SELECT COUNT(*) FROM profiles p LEFT JOIN participants a ON a.id=p.participant_id "
        "WHERE a.id IS NULL"
    )
    checks["sessions_without_participant"] = _scalar(
        "SELECT COUNT(*) FROM sessions s LEFT JOIN participants a ON a.id=s.participant_id "
        "WHERE a.id IS NULL"
    )
    checks["responses_without_session"] = _scalar(
        "SELECT COUNT(*) FROM responses r LEFT JOIN sessions s ON s.id=r.session_id "
        "WHERE s.id IS NULL"
    )
    checks["responses_without_session_item"] = _scalar(
        "SELECT COUNT(*) FROM responses r LEFT JOIN session_items i ON i.id=r.session_item_id "
        "WHERE i.id IS NULL"
    )
    checks["responses_without_scenario"] = _scalar(
        "SELECT COUNT(*) FROM responses r LEFT JOIN scenarios sc ON sc.scenario_id=r.scenario_id "
        "WHERE sc.scenario_id IS NULL"
    )
    checks["session_items_without_scenario"] = _scalar(
        "SELECT COUNT(*) FROM session_items i LEFT JOIN scenarios sc "
        "ON sc.scenario_id=i.scenario_id WHERE sc.scenario_id IS NULL"
    )
    checks["mcv_without_profile"] = _scalar(
        "SELECT COUNT(*) FROM profile_mcv m LEFT JOIN profiles p "
        "ON p.participant_id=m.participant_id WHERE p.participant_id IS NULL"
    )

    # -- the response's recorded signal must match its own permutation --------
    # This is the check that would catch a display-position off-by-one, which is
    # exactly the bug class the runner hit from the other side.
    checks["responses_with_signal_not_matching_permutation"] = _scalar(
        "SELECT COUNT(*) FROM responses r WHERE r.chosen_signal <> "
        "JSON_UNQUOTE(JSON_EXTRACT(r.display_permutation, "
        "CONCAT('$[', r.chosen_display_position - 1, ']')))"
    )
    checks["responses_with_position_out_of_range"] = _scalar(
        "SELECT COUNT(*) FROM responses r WHERE r.chosen_display_position < 1 "
        "OR r.chosen_display_position > JSON_LENGTH(r.display_permutation)"
    )

    # -- session composition, against MIMIC's own declared length ------------
    checks["completed_sessions_with_wrong_item_count"] = _scalar(
        f"SELECT COUNT(*) FROM (SELECT s.id, COUNT(i.id) n FROM sessions s "
        f"JOIN session_items i ON i.session_id=s.id WHERE s.state='COMPLETED' "
        f"GROUP BY s.id HAVING n <> {session_length}) x"
    )
    checks["completed_sessions_with_unanswered_items"] = _scalar(
        "SELECT COUNT(DISTINCT s.id) FROM sessions s JOIN session_items i "
        "ON i.session_id=s.id WHERE s.state='COMPLETED' AND i.answered_at IS NULL"
    )
    checks["sessions_without_exactly_one_probe_repeat"] = _scalar(
        "SELECT COUNT(*) FROM (SELECT s.id, SUM(i.is_probe_repeat) k FROM sessions s "
        "JOIN session_items i ON i.session_id=s.id WHERE s.state='COMPLETED' "
        "GROUP BY s.id HAVING k <> 1) x"
    )
    checks["duplicate_response_per_item"] = _scalar(
        "SELECT COUNT(*) FROM (SELECT session_item_id, COUNT(*) c FROM responses "
        "GROUP BY session_item_id HAVING c > 1) x"
    )

    # -- value domains --------------------------------------------------------
    checks["responses_with_illegal_signal"] = _scalar(
        "SELECT COUNT(*) FROM responses WHERE chosen_signal NOT IN ('SO','RC','CP','AL')"
    )
    checks["profiles_with_likert_out_of_range"] = _scalar(
        "SELECT COUNT(*) FROM profiles WHERE environmental_concern NOT BETWEEN 1 AND 5 "
        "OR trust_in_automation NOT BETWEEN 1 AND 5 "
        "OR comfort_sensitivity NOT BETWEEN 1 AND 5"
    )
    checks["mcv_items_out_of_range"] = _scalar(
        "SELECT COUNT(*) FROM profile_mcv WHERE " + " OR ".join(
            f"mcv_{i:02d} NOT BETWEEN 1 AND 5" for i in range(1, 11)
        )
    )
    checks["profiles_with_wrong_schema_version"] = _scalar(
        "SELECT COUNT(*) FROM profiles WHERE schema_version <> '1.1'"
    )

    # -- ADR-004: the forbidden columns must not exist at all ----------------
    checks["forbidden_columns_present"] = _scalar(
        "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='mimic' "
        "AND COLUMN_NAME IN ('health_status','fitness_level','mobility_limitation',"
        "'medical_device_dependence','country_of_birth')"
    )

    counts = {
        "participants": _scalar("SELECT COUNT(*) FROM participants"),
        "profiles": _scalar("SELECT COUNT(*) FROM profiles"),
        "profiles_synthetic": _scalar(
            "SELECT COUNT(*) FROM profiles WHERE consent_version LIKE 'SYNTHETIC%'"
        ),
        "profile_mcv": _scalar("SELECT COUNT(*) FROM profile_mcv"),
        "sessions": _scalar("SELECT COUNT(*) FROM sessions"),
        "sessions_completed": _scalar("SELECT COUNT(*) FROM sessions WHERE state='COMPLETED'"),
        "sessions_abandoned": _scalar("SELECT COUNT(*) FROM sessions WHERE state='ABANDONED'"),
        "session_items": _scalar("SELECT COUNT(*) FROM session_items"),
        "responses": _scalar("SELECT COUNT(*) FROM responses"),
        "scenarios": _scalar("SELECT COUNT(*) FROM scenarios"),
    }
    consent_versions = {
        row[0]: int(row[1])
        for row in mysql_query(
            "SELECT consent_version, COUNT(*) FROM profiles GROUP BY consent_version"
        )
    }
    probe_agreement = mysql_query(
        "SELECT COALESCE(SUM(probe_agreement),0), COUNT(probe_agreement) FROM sessions "
        "WHERE probe_agreement IS NOT NULL"
    )
    agreed, scored = (
        (int(probe_agreement[0][0]), int(probe_agreement[0][1])) if probe_agreement else (0, 0)
    )

    return {
        "checks": checks,
        "total_integrity_errors": sum(checks.values()),
        "counts": counts,
        "consent_versions": consent_versions,
        "probe_agreement": {
            "sessions_scored": scored,
            "agreed": agreed,
            "agreement_rate": round(agreed / scored, 4) if scored else None,
        },
        "session_length_expected": session_length,
    }


def grand_mean_pi_from_db() -> dict[str, Any]:
    """MIMIC's ``grand_mean_pi``, recomputed independently in SQL.

    T9 asks whether the dashboard's published aggregate matches the same
    statistic computed independently over the same data.  Computing it here,
    from the database rather than from the runner's own records, removes two
    sources of spurious disagreement - which population, and in which order the
    floats were accumulated - so that any residual difference is a real
    dashboard defect rather than an artefact of the comparison.

    Both variants are returned, because the difference between them is itself a
    finding: MIMIC's value sits about 3e-6 from a rounding boundary, so the
    fourth decimal place it publishes flips depending on accumulation order.
    """
    expr = ("CASE r.chosen_signal WHEN 'SO' THEN 0 WHEN 'RC' THEN 1 "
            "WHEN 'CP' THEN 2 WHEN 'AL' THEN 3 END / 3.0")
    plain = mysql_query(
        f"SELECT AVG(pm), COUNT(*) FROM (SELECT r.participant_id, AVG({expr}) pm "
        f"FROM responses r GROUP BY r.participant_id) x"
    )[0]
    joined = mysql_query(
        f"SELECT AVG(pm), COUNT(*) FROM (SELECT r.participant_id, AVG({expr}) pm "
        f"FROM responses r INNER JOIN session_items si ON si.id = r.session_item_id "
        f"INNER JOIN profiles p ON p.participant_id = r.participant_id "
        f"GROUP BY r.participant_id) x"
    )[0]
    response_level = mysql_query(
        f"SELECT AVG({expr}), COUNT(*) FROM responses r"
    )[0]
    return {
        "participant_weighted": float(plain[0]),
        "participant_weighted_with_dashboard_joins": float(joined[0]),
        "n_participants": int(plain[1]),
        "response_level": float(response_level[0]),
        "n_responses": int(response_level[1]),
        "statistic": (
            "DashboardQuery::grandMeans takes Stats::mean of per-participant "
            "mean PI, so this is an unweighted mean of participant means"
        ),
    }


#: Where MIMIC's document root sits inside the web container.  Checked rather
#: than assumed by :func:`_dashboard_via_cli`.
MIMIC_WEBROOT = "/var/www/html/mimic"

#: The CLI harness.  It sets up exactly the request state ``api/dashboard.php``
#: reads - the method, the ADR-005 researcher token header, and ``?fresh`` -
#: and then runs **MIMIC's own endpoint**, unmodified.  ``header()`` and
#: ``http_response_code()`` are no-ops under the CLI SAPI and
#: ``JsonResponse::ok`` echoes the same JSON body, so the payload is identical
#: to the one nginx would have returned.
_DASHBOARD_CLI = """<?php
$_SERVER['REQUEST_METHOD'] = 'GET';
$_SERVER['HTTP_X_MIMIC_RESEARCHER_TOKEN'] = getenv('MIMIC_TOKEN');
$_GET = __GET__;
require '__ROOT__/api/dashboard.php';
"""


#: The v2-only harness (I-088).  It assembles the payload from **MIMIC's own**
#: ``DashboardBundle``, ``DashboardFilters`` and ``ResultsSnapshotService``,
#: using the same expressions ``api/dashboard.php`` uses for every key T9
#: reads, and skips exactly one thing: ``DashboardAnalytics::bundle()``.
#:
#: Why that is not a weakened test.  T9 checks four things -
#: ``v2.quality.grand_mean_pi``, ``min_n``, the synthetic banner, and the
#: cell-suppression scan over the v2 blocks - and every one of them is a v2
#: field or one of the literals ``api/dashboard.php`` merges in. The only
#: legacy-sourced key T9 touches at all is ``summary.grand_mean_pi``, as a
#: fallback when the v2 value is missing, and ``api/dashboard.php`` overwrites
#: that very field with the v2 value:
#:
#:     $legacy['summary']['grand_mean_pi'] = $v2['quality']['grand_mean_pi'] ?? null;
#:
#: so it cannot carry information the v2 block does not already have. The
#: legacy bundle is, for T9's purposes, an unused computation - and it is the
#: one with no established upper bound at this scale (over 1,000 s, abandoned
#: twice, most recently at 20 minutes with no end in sight).
_DASHBOARD_CLI_V2 = """<?php
require '__ROOT__/bootstrap.php';
use Mimic\\DashboardBundle;
use Mimic\\DashboardFilters;
use Mimic\\ResultsSnapshotService;
$pdo = mimic_db();
$filters = new DashboardFilters();
$snap = new ResultsSnapshotService();
$fresh = __FRESH__;
$v2 = $fresh ? DashboardBundle::compute($pdo, $filters, false) : $snap->assembleV2();
if ($v2 === null) {
    echo json_encode(['ok' => false, 'error' => 'no snapshot and fresh not requested']);
    exit(1);
}
$meta = $snap->readMeta();
global $MIMIC_APP;
$payload = [
    'version' => '2.0',
    'v2' => $v2,
    'pi_note' => 'Prosociality Index (PI): SO=0, RC=1, CP=2, AL=3, scaled 0-1.',
    'min_n' => DashboardFilters::MIN_N,
    'snapshot' => !$fresh,
    'live' => $fresh,
    'weighted' => $meta['weighted'] ?? false,
    'weighting_note' => $meta['weighting_note'] ?? 'none - post-stratification pending',
    'includes_synthetic' => (bool) ($v2['quality']['synthetic']['has_synthetic'] ?? false),
];
echo json_encode(['ok' => true, 'data' => $payload], JSON_UNESCAPED_UNICODE);
"""

#: What ``cli_v2`` does not compute, recorded so the artefact says it rather
#: than the reader having to infer it.
CLI_V2_SKIPPED = {
    "skipped": "DashboardAnalytics::bundle() (the legacy bundle)",
    "skipped_keys_not_read_by_t9": [
        "every legacy top-level key; api/dashboard.php merges them UNDER its "
        "own literals, so min_n, includes_synthetic, weighted, weighting_note, "
        "snapshot and live are the literals either way"
    ],
    "only_legacy_key_t9_touches": (
        "summary.grand_mean_pi, and only as a fallback when "
        "v2.quality.grand_mean_pi is absent - which api/dashboard.php itself "
        "overwrites with the v2 value, so it carries no independent information"
    ),
    "computed_in_full": (
        "DashboardBundle::compute (all seven v2 blocks, fresh) plus the same "
        "top-level literals api/dashboard.php adds"
    ),
    "t9_unchanged": (
        "same statistic (v2.quality.grand_mean_pi), same min_n, same synthetic "
        "banner, same cell-suppression scan over the same blocks, same pass "
        "criterion"
    ),
    "issue": "I-088",
}


def _dashboard_via_cli_v2(
    *, fresh: bool, timeout: int, container: str
) -> dict[str, Any]:
    """The v2 bundle and T9's literals, from MIMIC's own classes, no legacy bundle."""
    script = (
        _DASHBOARD_CLI_V2
        .replace("__FRESH__", "true" if fresh else "false")
        .replace("__ROOT__", MIMIC_WEBROOT)
    )
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "php"],
        input=script, capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout
    start = out.find("{")
    if start < 0:
        raise RuntimeError(
            f"dashboard v2 via PHP CLI produced no JSON (exit {proc.returncode}): "
            f"stdout={out[:300]!r} stderr={proc.stderr[:300]!r}"
        )
    doc = json.loads(out[start:])
    if not doc.get("ok"):
        raise RuntimeError(f"dashboard v2 failed: {doc.get('error')}")
    return doc["data"]


def _dashboard_via_cli(
    *, token: str, fresh: bool, timeout: int, container: str
) -> dict[str, Any]:
    """Run MIMIC's own dashboard endpoint under the container's PHP CLI.

    **Why this transport exists** (ISSUES.md I-088).  ``api/dashboard.php``
    calls ``DashboardAnalytics::bundle()`` on every request, whatever ``fresh``
    is, and that is CPU-bound PHP rather than SQL - measured with the web
    container pinned at 100% CPU and MySQL idle at 0.8%.  At the waved panel's
    23,456 participant rows it runs past the **600 s**
    ``fastcgi_read_timeout`` that MIMIC ships in ``docker/nginx/default.conf``,
    so nginx returns ``504 Gateway Time-out`` and the endpoint cannot be served
    over HTTP at this scale at all.  Measured: HTTP 504 at 600.06 s with a
    client ``--max-time`` of 5400 s, so the limit is the server's and not the
    caller's.

    What this changes is **only the transport**.  It is MIMIC's own
    ``api/dashboard.php``, with MIMIC's own token check, producing MIMIC's own
    payload; nothing in the MIMIC tree is modified, and the ``fresh`` flag is
    passed through unchanged so the same bundle is computed.  What it does not
    change is what T9 tests: the same ``v2.quality.grand_mean_pi``, the same
    ``min_n``, the same synthetic banner and the same cells, against the same
    pass criterion.

    The alternative - raising ``fastcgi_read_timeout`` - would have been an
    edit to MIMIC's shipped configuration, which the standing rule forbids
    doing silently.  It is recorded as I-088 instead.
    """
    script = (
        _DASHBOARD_CLI
        .replace("__GET__", "['fresh' => '1']" if fresh else "[]")
        .replace("__ROOT__", MIMIC_WEBROOT)
    )
    proc = subprocess.run(
        ["docker", "exec", "-i", "-e", f"MIMIC_TOKEN={token}", container, "php"],
        input=script, capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout
    start = out.find("{")
    if proc.returncode != 0 or start < 0:
        raise RuntimeError(
            f"dashboard via PHP CLI failed (exit {proc.returncode}): "
            f"stdout={out[:300]!r} stderr={proc.stderr[:300]!r}"
        )
    try:
        doc = json.loads(out[start:])
    except ValueError as exc:
        raise RuntimeError(
            f"dashboard via PHP CLI returned non-JSON: {out[start:][:300]!r}"
        ) from exc
    if not doc.get("ok"):
        raise RuntimeError(f"dashboard failed: {doc.get('error')}")
    return doc["data"]


def fetch_dashboard_with_transport(
    base_url: str,
    *,
    token: str = RESEARCHER_TOKEN,
    fresh: bool = True,
    timeout: int = 600,
    transport: str = "auto",
    container: str = "bailenua-mimic-local-web-1",
    http_probe_timeout: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The dashboard bundle, and how it was obtained.

    ``transport``:

    * ``"http"`` - over the public HTTP endpoint, as a researcher's browser
      would.  The only transport until the waved panel made it return 504.
    * ``"cli"`` - MIMIC's own ``api/dashboard.php`` under the container's PHP
      CLI, with nginx's ``fastcgi_read_timeout`` out of the path (I-088).  This
      still runs the legacy bundle, which has no established upper bound at
      23,456 participant rows.
    * ``"cli_v2"`` - the v2 bundle and T9's literals from MIMIC's own classes,
      skipping only ``DashboardAnalytics::bundle()``, which T9 does not read
      (see :data:`CLI_V2_SKIPPED`).
    * ``"auto"`` - HTTP first, then ``cli_v2``.  Which one answered is returned,
      so the artefact records it rather than the reader having to assume.
    """
    meta: dict[str, Any] = {
        "transport_requested": transport, "fresh": fresh,
        "http_timeout_s": http_probe_timeout if transport == "auto" else timeout,
    }
    if transport in ("http", "auto"):
        t0 = time.time()
        try:
            r = requests.get(
                f"{base_url.rstrip('/')}/api/dashboard.php",
                params={"fresh": "1"} if fresh else {},
                headers={"X-MIMIC-Researcher-Token": token},
                timeout=(http_probe_timeout or timeout),
            )
            # The STATUS first, and the body only if the status allows it.
            # Parsing first recorded the 504 as
            # "JSONDecodeError: Expecting value: line 1 column 1" - true, and
            # useless, because nginx's 504 body is HTML. The status code is the
            # evidence for I-088 and it must be what the artefact carries.
            meta["http_status"] = r.status_code
            if r.status_code != 200:
                reason = f"HTTP {r.status_code}: {r.text[:120]!r}"
            else:
                try:
                    doc = r.json()
                except ValueError as exc:
                    reason = f"HTTP 200 but non-JSON body ({exc})"
                else:
                    if doc.get("ok"):
                        meta.update(transport_used="http",
                                    seconds=round(time.time() - t0, 1))
                        return doc["data"], meta
                    reason = f"HTTP 200 with ok=false: {doc.get('error')}"
        except requests.RequestException as exc:
            reason = f"{type(exc).__name__}: {exc}"
        meta["http_failed_after_s"] = round(time.time() - t0, 1)
        meta["http_failure"] = reason[:200]
        if transport == "http":
            raise RuntimeError(f"dashboard over HTTP failed: {reason[:300]}")

    t0 = time.time()
    if transport == "cli":
        data = _dashboard_via_cli(
            token=token, fresh=fresh, timeout=timeout, container=container
        )
        meta.update(transport_used="cli")
    else:
        data = _dashboard_via_cli_v2(
            fresh=fresh, timeout=timeout, container=container
        )
        meta.update(transport_used="cli_v2", **CLI_V2_SKIPPED)
    meta.update(seconds=round(time.time() - t0, 1),
                cli_timeout_s=timeout, container=container)
    meta.setdefault("issue", "I-088: the HTTP endpoint 504s at this scale")
    return data, meta


def fetch_dashboard(
    base_url: str, *, token: str = RESEARCHER_TOKEN, fresh: bool = True,
    timeout: int = 600, transport: str = "http",
) -> dict[str, Any]:
    """Fetch MIMIC's researcher dashboard bundle (ADR-005 token required).

    Kept returning just the payload so existing callers are unchanged; use
    :func:`fetch_dashboard_with_transport` when the transport matters.
    """
    data, _ = fetch_dashboard_with_transport(
        base_url, token=token, fresh=fresh, timeout=timeout, transport=transport
    )
    return data


def purge_synthetic(*, dry_run: bool = True) -> dict[str, Any]:
    """Exercise MIMIC's own synthetic purge predicate (design 9.3 day 3).

    MIMIC identifies synthetic rows by ``consent_version LIKE 'SYNTHETIC%'``
    (``mimic_sd_generator.php`` line 628), which is why design 5.14 chose that
    marker: the existing purge and banner work unchanged.  This counts what the
    predicate would remove and, when ``dry_run`` is False, removes it and
    confirms nothing is left.

    Cascade deletes are declared on every child table
    (``ON DELETE CASCADE`` from ``participants``), so deleting the participants
    is sufficient - which is itself worth verifying rather than assuming.
    """
    before = {
        "profiles_synthetic": _scalar(
            "SELECT COUNT(*) FROM profiles WHERE consent_version LIKE 'SYNTHETIC%'"
        ),
        "participants": _scalar("SELECT COUNT(*) FROM participants"),
        "responses": _scalar("SELECT COUNT(*) FROM responses"),
        "sessions": _scalar("SELECT COUNT(*) FROM sessions"),
    }
    if dry_run:
        return {
            "dry_run": True,
            "predicate": "consent_version LIKE 'SYNTHETIC%'",
            "would_remove": before,
            "all_removed": None,
            "note": "not executed; pass dry_run=False to purge",
        }

    mysql_query(
        "DELETE FROM participants WHERE id IN "
        "(SELECT participant_id FROM profiles WHERE consent_version LIKE 'SYNTHETIC%')"
    )
    after = {
        "profiles_synthetic": _scalar(
            "SELECT COUNT(*) FROM profiles WHERE consent_version LIKE 'SYNTHETIC%'"
        ),
        "participants": _scalar("SELECT COUNT(*) FROM participants"),
        "responses": _scalar("SELECT COUNT(*) FROM responses"),
        "sessions": _scalar("SELECT COUNT(*) FROM sessions"),
        "orphan_profiles": _scalar(
            "SELECT COUNT(*) FROM profiles p LEFT JOIN participants a "
            "ON a.id=p.participant_id WHERE a.id IS NULL"
        ),
        "orphan_responses": _scalar(
            "SELECT COUNT(*) FROM responses r LEFT JOIN participants a "
            "ON a.id=r.participant_id WHERE a.id IS NULL"
        ),
    }
    return {
        "dry_run": False,
        "predicate": "consent_version LIKE 'SYNTHETIC%'",
        "before": before,
        "after": after,
        "all_removed": (
            after["profiles_synthetic"] == 0
            and after["orphan_profiles"] == 0
            and after["orphan_responses"] == 0
        ),
        "cascade_verified": after["orphan_profiles"] == 0 and after["orphan_responses"] == 0,
    }
