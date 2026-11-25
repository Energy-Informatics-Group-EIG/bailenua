# ops/ — running Baile Nua v1 on this instance

Everything here sits outside the frozen repo. Nothing changes `scripts/baile_nua`
(the engine digest) or `scripts/replay_config.json`.

| file | what it does |
|---|---|
| `env.sh`, `lib.sh` | shared paths and helpers (`alert`, `block`, `current_segment`) |
| `run_supervisor.sh` | `ExecStart` of `baile-nua-v1.service`: runs `pre_start.sh`, then `replay_supervisor.py` (one child per year) |
| `pre_start.sh` | run first by `run_supervisor.sh`: post-pass-only recovery and the loop guard (below); exit 78 = BLOCKED |
| `finish_segment.py` | finishes a segment whose simulation completed: U27, export, checks, `DONE.json`. Also applies the PL-TEMP-01 override and the 2023–2026 peak-RSS gate exception (below) |
| `watch_tick.sh` | every 10 min: one line to `hrsd/logs/watch.log`, `status/HOST.txt` |
| `watchdog.sh` | every 10 min: alerts, in-process retry detection, loop guard |
| `post_year.sh` | every 10 min: `verify_segment`, key scan, B2 upload, `rclone check`, emails per year and at completion |
| `morning.sh`, `morning_email.sh` | 08:00 Irish time: `status/MORNING.md`, emailed |
| `notify.sh`, `msmtprc`, `mail_password.sh` | email via smtp.gmail.com:587. The app password is parsed from `~/.mail_baile_nua.env` at send time; it is never sourced, printed or logged |
| `release_fill.py` | fills `hrsd/docs/*.draft.md` (release notes, provenance, limitations) from the run records and re-checks the drafts' every-year claims. `--partial --out <dir>` previews; writing the final names into `hrsd/docs` is refused until 13 DONE and 12 UPLOADED |
| `systemd/` | the installed unit files (`/etc/systemd/system/baile-nua-*`) |

## Restart policy

* **The simulation finished; the post-pass failed** (U27, export, checks, scan).
  The checkpoints and package are complete, so only the post-pass is re-run
  (`finish_segment.py`, from `pre_start.sh`). It calls the same functions in the
  same order as `run_year` and `replay_supervisor.main`. It was tested on a copy
  of the smoke run with the post-pass undone: every data Parquet file came out
  byte-identical, and D23 differed only in its run start and end times, which it
  takes from file timestamps.
  If the supervisor itself retries such a segment in-process (renames it aside and
  starts again from day 0), `watchdog.sh` stops the service, moves the new attempt
  aside as `<seg>.superseded.<ts>`, puts the finished attempt back, and restarts.
* **A crash during the simulation.** The supervisor renames the attempt aside and
  re-runs the segment from the previous segment's final checkpoint (D-135). A
  mid-year resume from the latest daily checkpoint is **not** done, because it
  cannot reproduce the package an uninterrupted year writes:
  `run_year` holds whole-year state in memory and only writes it at the end
  (`annual_wh` → D24, the sleep statistics, energy closure, `benchmark.n_days`,
  which `check_year` requires to equal the segment length). Rows since the last
  30-day flush exist only in memory. `StreamWriter` numbers its parts from 0.
  Doing it needs engine changes, which is v2 (`docs/V2_PLAN.md`).
* **Nothing is deleted.** Every attempt is kept as `<seg>.partial.<ts>` or
  `<seg>.superseded.<ts>`.

## Loop guard

A segment's failures = attempts renamed aside + a dead attempt found at start +
failed post-pass recoveries. When a segment reaches **2**, the run stops:
`status/BLOCKED.md` is written, the service is stopped (or not started), and an
email goes out. Inside the unit the guard exits **78**, and
`RestartPreventExitStatus=78` makes that a final stop; `ConditionPathExists=!…/BLOCKED.md`
keeps a manual start or a boot from starting it. Both halves are needed, and the
guard must run in `ExecStart`, not `ExecStartPre`. Tested on this host:
`RestartPreventExitStatus` is ignored for `ExecStartPre` failures, and the
condition is not re-checked on automatic restarts. Until 17 Oct the guard ran in
`ExecStartPre` and exited 1, so a BLOCKED 2020 restarted every 2 min. To resume: fix the cause, remove `BLOCKED.md`, then
`sudo systemctl start baile-nua-v1`.

## Alerts (subject prefix `[Baile Nua v1]`)

BLOCKED or UPLOAD_FAILED · service restarted · an attempt renamed aside · no new
simulated day for 30 min (during the post-run phase, which writes no
checkpoints by design, only after 3 h) · child RSS > 40 GB (expected once a
year, at U27) · swap > 50 % · disk free < 40 GB · each year uploaded (rows, GB,
`rclone check`) · 08:00 MORNING.md · completion. Each condition emails once
when it starts and re-arms when it clears. Log of sends: `logs/alerts.log`.

Testing: `RUN=… STATE=… STATUS=… NOTIFY_DRYRUN=1 SYSTEMCTL=echo bash pre_start.sh`.

## End of v1: auto-stop guard (`end_guard.sh`)

Runs as the last step of every 10-minute ops tick. Disabled while `ops/NO_STOP`
exists (`touch ~/hrsd_occupants/ops/NO_STOP`).

1. **Complete** only when all of these hold: 13 DONE; 2015–2026 each UPLOADED
   with `rclone check` showing 0 differences; `docs/PROVENANCE.md`,
   `RELEASE_NOTES_v1.md` and `V1_KNOWN_LIMITATIONS.md` on `v1/docs/` and
   checked; then a final full check: `v1/` holds exactly `2015..2026` and
   `docs`, each year's `pkg` and `_segment` checked two-way, docs checked.
   For 2015–2019 the local Parquet was deleted on 2026-10-18 (Brian), each year
   only after `rclone check --one-way` against B2 showed 0 differences. For those
   years the rest of `pkg` is still checked two-way, and the Parquet on B2 is
   checked with `rclone checksum sha1` against `state/<year>.parquet.sha1`, saved
   from the local files before deletion. Logs: `logs/prune_<year>.log`.
   → email "[Baile Nua v1] COMPLETE" (rows, GB, B2 paths, runtime, cost estimate).
2. **Is the shared instance in use?** Any process with cwd or arguments under
   `~/hrsd` (not `~/hrsd_occupants`), any tmux session whose name does not
   contain baile/occupants, any SSH login (`who`; this includes your own), or
   more than 1.5 cores of CPU outside the `baile-nua-*` units over 5 min.
   → if yes: email "complete, instance left running: <reason>", recheck hourly,
   give up after 24 h and email.
3. **If clear:** email "stopping instance in 15 min" and start a transient
   `baile-nua-autostop` timer for +10 min. That step re-checks NO_STOP and the
   confirmation file, takes a fresh 5-minute activity sample (ending about 15
   min after the warning), then runs `sudo shutdown -h now`.
4. **Never terminate.** The instance's shutdown behaviour cannot be read from
   here (no AWS CLI or IAM role), and an OS shutdown terminates an instance set
   to "terminate". So the guard shuts down only if
   `ops/SHUTDOWN_BEHAVIOR_IS_STOP` exists. Create that file only after the
   console shows *Change shutdown behavior = Stop*.

Dry run: `bash end_guard.sh tick --dry-run` (no email, no timer, no shutdown).

## Accepted U27 exceedance: PL-TEMP-01 (approved by Brian, 2026-10-17)

From 2020, `finish_segment.py` (`TEMP_OVERRIDE`) accepts a PL-TEMP-01 FAIL
(indoor peak above the declared, unsourced 40 °C) only while: peak ≤ 45 °C,
median 17.80–20.01 °C (2015–2019 range ± 1 °C), share above 28 °C ≤ 0.5 %, and
no other check fails. Otherwise the year blocks as before. The acceptance goes
into `DONE.json` as `u27_accepted_exceedances`; `evidence/plausibility.json` is
not touched. The engine's `KNOWN_PLAUSIBILITY_FAILURES` is frozen, so `run_year`
still raises in the child. The supervisor starts an in-process retry, the
watchdog (≤ 10 min) stops it, keeps it as `<seg>.superseded.<ts>`, restores the
finished attempt and restarts, and `pre_start.sh` finishes the year here. Each
such year costs up to 10 min plus the post-pass, not a re-simulation.

## Peak-RSS gate exception, 2023–2026 (approved by Brian, 2026-10-18)

`replay_supervisor.check_year` fails a year whose simulation peak RSS is above
`rss_gate_mb` (18432, frozen config). Peak RSS grows with D18 1-minute coverage
(2022 18.3 GB, 2023 23.7 GB), so every year from 2023 exceeds it. For 2023–2026
`finish_segment.py` (`RSS_OVERRIDE`) accepts that failure only while the peak is
≤ 40960 MB and it is the only failure, and records it in `DONE.json` as
`rss_gate_exception`. A v1 operational exception: no output is affected. The
year reaches `finish_segment.py` by the same route as PL-TEMP-01: the supervisor
fails it in-process, the watchdog restores the finished attempt and restarts.
The in-run gate never trips on Linux (current RSS is read in macOS units, 1000×
low). Swap is 200 GB (`/swapfile.baile-nua` 96G + `/swapfile.baile-nua-2` 104G,
both in fstab) because U27 used 94.2 GB of the original 96 GB in 2023. V2:
`docs/V2_PLAN.md` EC2-3.
