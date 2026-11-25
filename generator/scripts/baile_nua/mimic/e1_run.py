"""Rebuild the MIMIC panel and re-measure T1, T9 and T10 (E1 criterion 6).

    python -m baile_nua.mimic.e1_run --root /path/to/HRSD_Occupants

Why this exists at all: the 08 October artefact described a population that no
longer exists.  The population was regenerated on 11 October to fix I-069 (the
person-level age x economic-status joint had no age conditioning), and 986 of
2,917 people changed economic status.  The panel's linked participants are drawn
from that population, so the artefact was evidence about a model that had been
replaced - which the E1 report now refuses to count (I-082).  There was no
committed driver for the run: the 08 October figures came from a scratchpad
script.  This is the driver.

What it runs, in order, and why the order matters:

1. the safety checks (loopback only, and the G-B specification frozen before any
   MIMIC estimator touches its output);
2. **the purge, first**, with the project's own predicate, so nothing from a
   previous run is counted in this one;
3. the three batches - the linked panel in waves, the unlinked extended pool,
   and T10's planted-bias arm;
4. the forbidden-field negative probe;
5. the database integrity checks, MIMIC's own grand mean PI and the researcher
   dashboard - **before** the purge, because they read the rows;
6. D25 out of MIMIC's database and D26 out of the answer keys;
7. **the purge, last**, which is what T1's "purge removes all" checks;
8. T1, T9 and T10, and the artefact.

Every MIMIC batch is checkpointed to the work directory as it finishes, so a
failure in stages 4 to 8 does not mean running the batches again.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import time
from pathlib import Path
from typing import Any

from baile_nua.mimic import crosswalk, datasets as ds_mod, panel, provision, tests, verify
from baile_nua.mimic import willingness as wg
from baile_nua.mimic.counters import MimicCounters
from baile_nua.mimic.extended_pool import generate_extended_pool
from baile_nua.mimic.runner import MimicRunner

__all__ = ["run", "main", "LABEL", "MASTER_SEED"]

LABEL = "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate"
CLAIM = "Engineering verification only. No behavioural calibration is claimed."

#: The frozen population's seed.  ``synthesise_t0(master_seed=20261008)``.
MASTER_SEED = 20261008

#: The unlinked extended pool's size.  U16 / I-007: the E1 target of 10,000
#: unique participants is met by the unlinked pool, because 50 homes do not
#: contain 10,000 adults.  Kept at the approved size so the criterion is met the
#: way it was approved - by 10,000 distinct people - and not by counting one
#: person's repeat waves.
N_POOL = 10_050

#: T10's planted arm.  Same size as the audited arm so the measured power in the
#: E1 report stays comparable.
N_PLANTED = 600
PLANTED_POSITION_BIAS = 1.6

#: Client read timeout for MIMIC's researcher dashboard, in seconds.
#:
#: Was ``verify.fetch_dashboard``'s own 600 s default, and the first waved-panel
#: run died on it at 23,456 participant rows after every batch had completed -
#: nine hours of inserts behind a client that gave up. The server has no limit
#: of its own (``max_execution_time = 0``), so this is purely how long the
#: caller is prepared to wait. Recorded as I-088 with the measured time.
DASHBOARD_TIMEOUT_S = 5400

#: How long to give MIMIC's HTTP dashboard endpoint before falling back to the
#: CLI transport. Deliberately longer than nginx's own 600 s
#: ``fastcgi_read_timeout`` so that what the artefact records is MIMIC's **504**
#: rather than our client giving up first - the distinction is the whole of
#: I-088, and a client-side timeout would have left it looking like our
#: impatience.
HTTP_PROBE_TIMEOUT_S = 660


def _dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(obj, fh, protocol=4)


def _load(path: Path) -> Any:
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _say(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def _batch(
    runner: MimicRunner,
    people: list[Any],
    *,
    name: str,
    pool: str,
    workers: int,
    sandbox: Path,
    work: Path,
    planted_position_bias: float = 0.0,
    frozen_spec: Path | None = None,
    reuse: bool = True,
) -> Any:
    ck = work / f"batch_{name}.pkl"
    if reuse and ck.is_file():
        _say(f"{name}: reusing checkpoint {ck.name}")
        return _load(ck)
    # I-026: the marker must be LIVE in the running instance before a single
    # participant is created, or the batch is tagged with the previous pool's
    # code. Retried rather than abandoned: the verification probe is four HTTP
    # round trips plus a docker exec per iteration and this machine is shared,
    # so a single attempt can run out of deadline without anything being wrong.
    marker: dict[str, Any] = {}
    for attempt in range(3):
        marker = provision.set_consent_version(sandbox, pool)
        if marker.get("verified_live"):
            break
        _say(f"{name}: consent marker not live yet (attempt {attempt + 1}/3)")
    if not marker.get("verified_live"):
        raise RuntimeError(
            f"the consent marker {marker['consent_version']!r} is not live in the "
            f"running instance after 3 attempts; starting the batch now would "
            f"mis-tag its pool (I-026)"
        )
    _say(f"{name}: {len(people)} participants, pool={pool}, "
         f"marker={marker['consent_version']}, workers={workers}")
    res = runner.run_batch(
        people, pool=pool, workers=workers,
        planted_position_bias=planted_position_bias,
        frozen_spec_path=frozen_spec,
        progress_every=500,
    )
    _say(f"{name}: {res.n_ok} created in {res.elapsed_s:.0f}s "
         f"({res.summary()['participants_per_second']}/s)")
    _dump(res, ck)
    return res


def run(
    *,
    root: Path,
    sandbox: Path,
    work: Path,
    workers: int = 2,
    n_pool: int = N_POOL,
    n_planted: int = N_PLANTED,
    reuse: bool = True,
    write_data: bool = True,
    panel_limit: int | None = None,
    artefact_path: Path | None = None,
    dashboard_timeout: int = DASHBOARD_TIMEOUT_S,
) -> dict[str, Any]:
    root, sandbox, work = Path(root), Path(sandbox), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # ---- 1. safety --------------------------------------------------------
    local = provision.assert_local_only(sandbox)
    frozen_spec = root / "v1" / "evidence" / "gb_willingness_spec_frozen.json"
    spec_hash = wg.assert_frozen(frozen_spec)
    _say(f"local only: {local['database_host']} {local['base_url']}; "
         f"G-B spec {spec_hash[:12]}")

    # ---- 2. the purge, FIRST ---------------------------------------------
    #
    # Only when batches are actually going to run. On a resume, every batch
    # comes back from a checkpoint and the rows in MIMIC are THAT run's rows:
    # purging them would leave the database empty while the checkpoints still
    # claim 23,000 participants, and the MIMIC-side reads would then describe
    # nothing at all. Found by doing it (grand_mean_pi returned NULL).
    batch_names = ("pool", "planted", "panel")
    # ANY checkpoint, not all three. A run that died between batches leaves the
    # completed batches' rows in MIMIC and their records on disk; purging then
    # would delete the data the checkpoints describe and leave the MIMIC-side
    # reads describing nothing. Found by doing it with all three (grand_mean_pi
    # returned NULL), and the partial case is the same fault.
    resuming = reuse and any(
        (work / f"batch_{n}.pkl").is_file() for n in batch_names
    )
    purge_before = verify.purge_synthetic(dry_run=True)
    if resuming:
        initial_purge = {
            "skipped": True,
            "reason": (
                "resumed from batch checkpoints; the synthetic rows in MIMIC "
                "are this run's own rows"
            ),
            "predicate": purge_before["predicate"],
            "before": purge_before["would_remove"],
            "after": purge_before["would_remove"],
            "all_removed": None,
        }
        _say(f"initial purge SKIPPED (resuming): {purge_before['would_remove']}")
    else:
        initial_purge = verify.purge_synthetic(dry_run=False)
        _say(f"initial purge: before={initial_purge['before']} "
             f"after={initial_purge['after']}")

    # ---- 3. the cohorts --------------------------------------------------
    pop_ck = work / "panel_people.pkl"
    if reuse and pop_ck.is_file():
        panel_people, panel_diag = _load(pop_ck)
        _say(f"panel: reusing {len(panel_people)} wave participants")
    else:
        from baile_nua.population.synthesise import synthesise_t0
        _say(f"synthesising the frozen population (master_seed={MASTER_SEED})")
        pop = synthesise_t0(master_seed=MASTER_SEED)
        panel_people, panel_diag = panel.build_panel(
            persons=pop.persons, states=pop.states, membership=pop.membership,
            buildings=pop.buildings_frame, master_seed=MASTER_SEED,
        )
        _dump((panel_people, panel_diag), pop_ck)
        _say(f"panel: {panel_diag['n_wave_participants']} wave participants from "
             f"{panel_diag['n_persons_with_at_least_one_wave']} people, "
             f"{panel_diag['n_waves_in_calendar']} waves "
             f"{panel_diag['wave_calendar'][0]}..{panel_diag['wave_calendar'][-1]}")

    if panel_limit is not None:
        # Smoke runs only: keep whole PEOPLE, never part of a person's waves,
        # so a truncated panel is still a panel.
        keep: set[str] = set()
        trimmed = []
        for p in panel_people:
            if str(p.linked_person_id) not in keep and len(keep) >= panel_limit:
                continue
            keep.add(str(p.linked_person_id))
            trimmed.append(p)
        panel_people = trimmed
        panel_diag = {**panel_diag, "panel_limit_applied": panel_limit,
                      "n_wave_participants": len(panel_people)}

    pool_people = generate_extended_pool(n_pool, master_seed=MASTER_SEED)
    planted_people = generate_extended_pool(
        n_planted, master_seed=MASTER_SEED + 1
    )
    # The planted arm's ids must not collide with the main pool's, or the two
    # arms would share seed-tree addresses and T10 would compare a batch with
    # part of itself.
    import dataclasses as _dc
    planted_people = [
        _dc.replace(p, pool_person_id=f"T10-{p.pool_person_id}")
        for p in planted_people
    ]

    runner = MimicRunner(sandbox=sandbox, master_seed=MASTER_SEED)

    # ---- 4. the batches ---------------------------------------------------
    # Order matters, and not for the data: the unlinked pool is what satisfies
    # E1-6's "at least 10,000 unique participants" (U16 / I-007) and T10's
    # planted arm is what makes T10 runnable, so both are done and
    # checkpointed BEFORE the long panel batch. A run that dies in the panel
    # then still has everything the E1 criterion needs. The two HRSD-pool
    # batches are also adjacent, so the consent marker is flipped once rather
    # than twice (I-026).
    pool_res = _batch(runner, pool_people, name="pool", pool="HRSD-pool",
                      workers=workers, sandbox=sandbox, work=work,
                      frozen_spec=frozen_spec, reuse=reuse)
    planted_res = _batch(runner, planted_people, name="planted",
                         pool="HRSD-pool", workers=workers, sandbox=sandbox,
                         work=work, planted_position_bias=PLANTED_POSITION_BIAS,
                         frozen_spec=frozen_spec, reuse=reuse)
    panel_res = _batch(runner, panel_people, name="panel", pool="BN-panel",
                       workers=workers, sandbox=sandbox, work=work,
                       frozen_spec=frozen_spec, reuse=reuse)

    # ---- 5. the forbidden-field negative probe ---------------------------
    probe_ck = work / "forbidden_probe.json"
    if reuse and probe_ck.is_file():
        forbidden_probe = json.loads(probe_ck.read_text())
    else:
        forbidden_probe = runner.probe_forbidden_fields()
        probe_ck.write_text(json.dumps(forbidden_probe, indent=2))
    _say(f"forbidden probe: {sum(1 for r in forbidden_probe if r['rejected'])}"
         f"/{len(forbidden_probe)} rejected")

    # ---- 6. the MIMIC-side reads, BEFORE the purge -----------------------
    integrity = verify.db_integrity()
    db_pi = verify.grand_mean_pi_from_db()
    _say(f"db integrity: {integrity['total_integrity_errors']} errors; "
         f"participants={integrity['counts']['participants']}")

    # ---- 7. D25 and D26 --------------------------------------------------
    clean_results = [*panel_res.participants, *pool_res.participants]
    planted_results = list(planted_res.participants)
    all_results = [*clean_results, *planted_results]
    clean_responses = [r for p in clean_results for r in p.responses]
    planted_responses = [r for p in planted_results for r in p.responses]

    written: dict[str, Any] = {}
    if write_data:
        d25, d25_diag = ds_mod.d25_frame()
        d26, d26_diag = ds_mod.d26_frame(
            [p.answer_key for p in all_results],
            planted_context_effect=wg.specification().context,
        )
        extra = {
            "label": LABEL, "claim": CLAIM,
            "mimic_schema_version": crosswalk.MIMIC_SCHEMA_VERSION,
            "gb_spec_hash": spec_hash,
            "population_master_seed": MASTER_SEED,
        }
        p25 = ds_mod.write_d25(d25, root, extra={**extra, **d25_diag})
        p26 = ds_mod.write_d26(d26, root, extra={**extra, **d26_diag})
        written = {
            "D25": {
                "path": str(p25), "rows": int(len(d25)),
                "bytes": p25.stat().st_size,
                "manifest_bytes": (p25.parent / f"{p25.stem}.manifest.json").stat().st_size,
                "columns": list(d25.columns), "diagnostics": d25_diag,
            },
            "D26": {
                "path": str(p26), "rows": int(len(d26)),
                "bytes": p26.stat().st_size,
                "manifest_bytes": (p26.parent / f"{p26.stem}.manifest.json").stat().st_size,
                "columns": list(d26.columns), "diagnostics": d26_diag,
            },
            "crosswalk_in_d26_only": {
                "person_id_in_D25_columns": "person_id" in d25.columns,
                "person_id_in_D26_columns": "person_id" in d26.columns,
            },
        }
        _say(f"D25 {len(d25)} rows -> {p25.name}; D26 {len(d26)} rows -> {p26.name}")

    # ---- 7b. the dashboard, AFTER D25/D26 are banked ---------------------
    #
    # Ordered last of the reads on purpose. D25 and D26 do not depend on the
    # dashboard at all, and the dashboard is the one step with no established
    # upper bound at this scale (I-088): the HTTP endpoint 504s and the legacy
    # bundle behind it ran past 1,000 s twice without finishing. Two datasets
    # we can have must not sit behind a statistic we might not get.
    #
    # TIMED, not just awaited, so the elapsed figure is evidence in the
    # artefact rather than something survived quietly.
    t_dash = time.time()
    dashboard, dash_meta = verify.fetch_dashboard_with_transport(
        runner.base_url, timeout=dashboard_timeout, transport="auto",
        http_probe_timeout=HTTP_PROBE_TIMEOUT_S,
    )
    dashboard_s = time.time() - t_dash
    _say(f"dashboard: {dash_meta['transport_used']} in {dashboard_s:.0f}s"
         + (f" (HTTP failed after {dash_meta['http_failed_after_s']}s: "
            f"{dash_meta['http_failure']})" if "http_failure" in dash_meta else ""))

    # ---- 8. the purge, LAST (T1's "purge removes all") -------------------
    final_purge = verify.purge_synthetic(dry_run=False)
    _say(f"final purge: before={final_purge['before']} after={final_purge['after']}")

    # ---- 9. the counters --------------------------------------------------
    counters = panel_res.counters + pool_res.counters + planted_res.counters
    cdict = counters.as_dict()
    cdict["_not_one_of_the_five"] = {
        **cdict.get("_not_one_of_the_five", {}),
        "rejected_forbidden_field_batches": sum(
            1 for r in forbidden_probe if r["rejected"]
        ),
        "mimic_participant_rows": int(integrity["counts"]["participants"]),
        "linked_panel_wave_sessions": int(panel_res.config["n_mimic_participant_rows"]),
        "t10_planted_arm_respondents": int(planted_res.counters.unique_participants),
    }
    cdict["_counting_rule"] = (
        "The five counters count RESPONDENTS. One linked panel person answers 8 "
        "to 15 waves and MIMIC's public API makes each wave a separate "
        "participant record (I-087), so MIMIC holds "
        f"{integrity['counts']['participants']} participant rows for "
        f"{cdict['unique_synthetic_participants']} respondents. The E1 report's "
        "own rule is that repeated sessions never count as unique participants."
    )
    cdict["_how_the_10000_is_met"] = (
        f"by the unlinked extended pool's {cdict['unlinked_extended_pool_participants']} "
        f"distinct people (U16 / I-007), not by repeat interviewing of the "
        f"{cdict['linked_baile_nua_panel_participants']} linked panel people."
    )

    # ---- 10. T1, T9, T10 --------------------------------------------------
    batch_summary = {"counters": cdict}
    t1 = tests.t1_api_and_schema_conformance(
        batch_summary=batch_summary, forbidden_probe=forbidden_probe,
        db_integrity=integrity, purge_result=final_purge,
    )
    t9 = tests.t9_dashboard_aggregates(
        dashboard, clean_responses + planted_responses, db_pi=db_pi,
    )
    t10 = tests.t10_position_bias(clean_responses, planted_responses)
    for t in (t1, t9, t10):
        _say(f"{t.test_id} {t.outcome} {t.detail}")

    artefact = {
        "label": LABEL,
        "claim": CLAIM,
        "measured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "elapsed_s": round(time.time() - t_start, 1),
        "population_master_seed": MASTER_SEED,
        "gb_spec_hash": spec_hash,
        "local_only": local,
        "counters": cdict,
        "panel": {**panel_diag, **{
            "batch": panel_res.summary(),
        }},
        "i075": {
            "issue": "the MIMIC panel exists and is not linked in time",
            "status": "addressed at the wave level; see mimic_change_required",
            "simulated_session_date_passed": True,
            "n_dated_panel_sessions": int(panel_res.config["n_dated_sessions"]),
            "n_distinct_simulated_session_dates": int(
                panel_res.config["n_distinct_simulated_session_dates"]
            ),
            "span": panel_res.config["simulated_session_date_span"],
            "sessions_per_person": panel_diag["sessions_per_person"],
            "mimic_change_required": (
                "MIMIC's JourneyService allows one session per participant, so a "
                "wave cannot reuse a participant id. Recorded as I-087; not "
                "fixed here."
            ),
        },
        "batches": {
            "panel": panel_res.summary(),
            "pool": pool_res.summary(),
            "planted": planted_res.summary(),
        },
        "db_integrity": integrity,
        "grand_mean_pi_from_db": db_pi,
        "purge": final_purge,
        "initial_purge": {
            "dry_run_before": purge_before.get("would_remove"),
            **initial_purge,
        },
        "dashboard_meta": {
            k: dashboard.get(k) for k in
            ("version", "min_n", "weighted", "weighting_note",
             "includes_synthetic", "snapshot", "live")
        },
        "dashboard_fetch": {
            **dash_meta,
            "total_seconds": round(dashboard_s, 1),
            "participant_rows": int(integrity["counts"]["participants"]),
            "responses": int(integrity["counts"]["responses"]),
            "note": (
                "I-088. MIMIC's HTTP dashboard endpoint returns 504 at this "
                "scale: nginx's fastcgi_read_timeout is 600 s and "
                "DashboardAnalytics::bundle() - which api/dashboard.php runs "
                "on EVERY request, whatever ?fresh is - exceeds it. Measured "
                "CPU-bound in PHP (web container 100%, MySQL 0.8%). The "
                "fallback runs MIMIC's OWN api/dashboard.php under the "
                "container's PHP CLI, so only the TRANSPORT changes: same "
                "endpoint, same token check, same ?fresh=1 bundle, and T9 "
                "tests the same statistic against the same criterion. "
                "Raising fastcgi_read_timeout would have been an edit to "
                "MIMIC's shipped config; it is recorded instead."
            ),
        },
        "datasets": written,
        "tests": [t.as_dict() if hasattr(t, "as_dict") else t.__dict__
                  for t in (t1, t9, t10)],
        "e1_criterion_6": {
            "criterion": (
                "MIMIC T1, T9 and T10 pass with at least 10,000 unique "
                "participants (5.14 counters)."
            ),
            "t1": t1.outcome, "t9": t9.outcome, "t10": t10.outcome,
            "unique_synthetic_participants": cdict["unique_synthetic_participants"],
            "target": 10_000,
            "verdict": (
                "PASS" if (t1.outcome == "PASS" and t9.outcome == "PASS"
                           and t10.outcome == "PASS"
                           and cdict["unique_synthetic_participants"] >= 10_000)
                else "FAIL"
            ),
        },
    }
    # D25 and D26 are DATA and belong in the delivered tree; the artefact is
    # EVIDENCE and is written where the caller says, because a parallel agent's
    # evidence is merged by the coordinator rather than dropped into the main
    # tree behind its back.
    out = Path(artefact_path) if artefact_path else (
        root / "v1" / "evidence" / "mimic_tests_T1_T10.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artefact, indent=2, default=str), encoding="utf-8")
    _say(f"artefact -> {out} (E1-6 {artefact['e1_criterion_6']['verdict']})")
    return artefact


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path,
                    help="the tree D25/D26 and the artefact are written under")
    ap.add_argument("--sandbox", type=Path,
                    default=Path("/Users/brianoregan/Desktop/HRSD_Occupants/work/mimic_local"))
    ap.add_argument("--work", type=Path, required=True,
                    help="checkpoint directory (not a release package)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--n-pool", type=int, default=N_POOL)
    ap.add_argument("--n-planted", type=int, default=N_PLANTED)
    ap.add_argument("--no-reuse", action="store_true",
                    help="ignore checkpoints and re-run every batch")
    ap.add_argument("--no-data", action="store_true", help="skip D25/D26")
    ap.add_argument("--panel-limit", type=int, default=None,
                    help="smoke runs only: cap the panel at this many PEOPLE")
    ap.add_argument("--artefact", type=Path, default=None,
                    help="where to write mimic_tests_T1_T10.json "
                         "(default: <root>/v1/evidence/)")
    ap.add_argument("--dashboard-timeout", type=int, default=DASHBOARD_TIMEOUT_S,
                    help="client read timeout for the researcher dashboard (s)")
    a = ap.parse_args(argv)
    run(root=a.root, sandbox=a.sandbox, work=a.work, workers=a.workers,
        n_pool=a.n_pool, n_planted=a.n_planted, reuse=not a.no_reuse,
        write_data=not a.no_data, panel_limit=a.panel_limit,
        artefact_path=a.artefact, dashboard_timeout=a.dashboard_timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
