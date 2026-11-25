# Baile Nua v1 (HRSD_Occupants): EC2 Run Specification

**Version:** 1.3 · **Date:** 17 October 2026 · **Owner:** Brian O'Regan, EIG, Tyndall National Institute, UCC
**Audience:** Claude Code (CC) on the Mac (preparation) and on the instance (run).
**Purpose:** run the frozen v1 replay (warm-up Dec 2014, then 1 Jan 2015 to 30 Sep 2026) on the existing EIG EC2 instance (shared with HRSD-RD_FUSION) so the Mac is free, then store every year on Backblaze B2.

**This instance:** `ubuntu@54.77.244.220`, project root **`~/hrsd_occupants/hrsd`** (unpacked from `~/hrsd_occupants/hrsd_occupants.tgz`). **`~/hrsd` is a different project (HRSD-RD_FUSION): never read, modify or run anything in it.**

---

## 1. Scope (frozen, do not change)

| Item | Value |
|---|---|
| Engine | tag `v1-engine-freeze-2.3` (code digest `05328f32…`) |
| Config | the v1 replay config as on the Mac (4,322 sim days incl. warm-up, continuous `sim_day`, one master seed, D-133) |
| Population | 2022 T0 population (P-7 accepted for v1 only) |
| Datasets | as `docs/V1_KNOWN_LIMITATIONS.md`: no D03/D09/D20, D12, D25/D26 |
| D18 | era-gated (smart meters from 2019-10-02, PARA//EL from 2021) |
| Changes allowed | none to engine, config or outputs. Fixes go to v2 (`docs/V2_PLAN.md`). |

v1 runs **entirely on the instance from the warm-up**, so every year comes from one platform (no Mac/Linux mix). The Mac's 2015 package is kept only as a cross-check.

## 2. Instance

| Item | Value | Why |
|---|---|---|
| Region | `eu-west-1` (Ireland) | data residency, latency |
| Type | **`r7a.xlarge`** (4 vCPU, 32 GB) | the chain is single-process; one fast core does the work, peak RSS ~12–16 GB. If `free -h` shows under 30 GB, stop and report |
| Upgrade if needed | `r7a.2xlarge` (8 vCPU, 64 GB) | only if post-passes or tests starve the run |
| Purchase | **On-demand** | multi-day serial run; a spot interruption costs a segment |
| OS | Ubuntu 24.04 LTS (x86_64) | |
| Disk | existing 290 GB root (~219 GB free) | ~65 GB data + checkpoints + sources + venv |
| Python | 3.12 (match the Mac's 3.12.6 minor version) | |
| Tools | git, uv or venv, rclone, tmux, gitleaks | |
| Network | security group: SSH (22) **from Brian's IP only**; no other inbound | |
| IAM | none needed | |
| Cost | approx. US$0.30–0.35/h for r7a.xlarge in eu-west-1, about US$30–40 for a 4–5 day run; check current AWS pricing | |

## 3. Security

1. **Before anything leaves the Mac:** secret scan of the repo (gitleaks plus grep for keys, passwords, tokens, `.env`, connection strings). Report counts only, never values. Anything flagged is excluded and listed in `docs/EC2_EXCLUDED.md`.
2. Never copy: `.venv/`, `~/.claude/`, `.claude/settings.local.json`, any `config.local.*`, unrelated repos, the home-directory git repo.
3. B2 key: bucket-scoped application key for `hrsd-occupants`, in `~/.b2_hrsd_occupants.env` (mode 600, outside the project tree). Sourced at run time into env vars `B2_KEY_ID`, `B2_APP_KEY` and the rclone remote vars `RCLONE_CONFIG_B2EIG_*` (no `rclone.conf`, no plaintext keys anywhere else). Never copied into the project, logs or shell history. `~/.b2.env` is the RD-Fusion key: never read or modify it for this project.
4. No secrets printed by CC at any point.
5. The instance is shared: **never terminate it, and CC never shuts it down by hand.** The only shutdown path is the auto-stop guard (`~/hrsd_occupants/ops/end_guard.sh`, §10), which stops the instance (`shutdown -h`, never terminate) only when v1 is verifiably complete, the instance is idle, and Brian has confirmed in the console that the instance's shutdown behaviour is *Stop* by creating `~/hrsd_occupants/ops/SHUTDOWN_BEHAVIOR_IS_STOP`. `touch ~/hrsd_occupants/ops/NO_STOP` disables the guard at any time.

## 4. What to transfer (Mac → instance)

| Copy | Exclude |
|---|---|
| repo at tag `v1-engine-freeze-2.3` (working tree) | `.venv/`, `work/` run outputs, `*.partial.*`, `worktrees/` |
| `requirements` lock (exact versions from the Mac venv) | any file flagged by the secret scan |
| `sources/` with all manifests and sha256 | |
| `config/` for the v1 replay | |
| `docs/` (incl. V1_KNOWN_LIMITATIONS, DECISIONS, RUN_DIGESTS) | |
| Mac `work/replay_2015_2026/2015/pkg` + `DONE.json` (cross-check only) | |

Done by Brian: `hrsd_occupants.tgz` (3.9 GB) built on the Mac from `~/hrsd` excluding `scripts/.venv`, `.venv`, `work/`, `.claude/`, `snapshots/`, `*.partial.*`, copied by `scp` to `~/hrsd_occupants/`. On the instance: unpack, then verify sha256 of `sources/` against manifests.

## 5. Setup on the instance

1. Install system packages and Python 3.12; create venv; install the locked requirements.
2. Verify the engine digest equals `05328f32…`. If not, stop.
3. Run the full test suite. Pass = same result as the Mac (only I-101 failing). Any other failure: stop and report.
4. **Smoke test:** warm-up plus 7 days at estate scale. Compare with the Mac's run of the same window. Report byte-identical or not (informational only; v1 runs fully on the instance either way).
5. **Kill/resume test:** kill mid-segment, restart, confirm identical checkpoints (as on the Mac).

## 6. Run

| Item | Value |
|---|---|
| Launcher | `replay_supervisor.py`, one subprocess per year, restored from the previous year's final checkpoint |
| Service | systemd unit `baile-nua-v1.service`, `WorkingDirectory=~/hrsd_occupants/hrsd`, `Restart=on-failure`, starts at boot |
| Checkpoints | daily state, parts flushed every 30 days |
| Memory gate | abort ceiling 24 GB current RSS; warning at 16 GB |
| Order | warm-up 2014 → 2015 → … → 2026 (to 30 Sep) |

**After each year completes:** export post-pass (all datasets in scope), `verify_segment`, secret/personal-data scan, package, upload, check.

## 7. Storage on Backblaze B2

| Item | Value |
|---|---|
| Bucket | `hrsd-occupants` (private), created by Brian |
| rclone remote | `b2eig` (type b2, defined only by `RCLONE_CONFIG_B2EIG_*` env vars from `~/.b2_hrsd_occupants.env`) |
| Layout | `b2eig:hrsd-occupants/v1/<year>/` per year; `b2eig:hrsd-occupants/v1/docs/` for provenance and release notes |
| Upload | `rclone copy --checksum --transfers 16 <pkg> b2eig:hrsd-occupants/v1/<year>/` |
| Verify | `rclone check --one-way` must report 0 differences before the year is marked UPLOADED |

## 8. Monitoring

- `status/PROGRESS.md` and `status/LAST.txt` updated every 10 min: year, % complete, s/day, RSS, disk free, ETA per year.
- `status/MORNING.md` at 08:00 Irish time.
- `status/BLOCKED.md` written on any failure after 2 retries; the run stops cleanly.
- Brian checks with: `ssh -i ~/.ssh/eig-hrsd.pem ubuntu@54.77.244.220 'cat ~/hrsd_occupants/hrsd/status/LAST.txt'`.
- CC on the instance only acts on BLOCKED or a crash: restart from checkpoint, change nothing else.

## 9. Handover from the Mac

1. The Mac run continues until the instance passes §5 and the warm-up and first 30 days on the instance are clean.
2. Then CC on the Mac stops the Mac replay and unloads its launchd agents (`ie.bailenua.replay`, `.watch`, `.morning`).
3. Mac outputs are kept, not deleted. The Mac's 2015 package is compared with the instance's 2015 (row counts and key aggregates) and the result goes in the release notes.

## 10. Finish

1. All years verified and uploaded, `rclone check` clean for each.
2. Write `PROVENANCE.md` (per dataset, as specified earlier), `RELEASE_NOTES_v1.md`, `V1_KNOWN_LIMITATIONS.md`; upload to `v1/docs/`.
3. Final report to Brian: per-year rows, sizes, B2 paths, total runtime and cost estimate.
4. **Auto-stop guard** (`ops/end_guard.sh`, run every 10 min by `baile-nua-ops.timer`; disabled while `ops/NO_STOP` exists):
   1. *Complete* only when all hold: 13 segments DONE; every year 2015–2026 uploaded with `rclone check` 0 differences; the three documents in item 2 on `v1/docs/` and checked; a final full `rclone check` of `v1/` against local clean (exactly `2015…2026` and `docs` at the top level; each year's package and `_segment` metadata checked both ways). Then email "[Baile Nua v1] COMPLETE" with per-year rows, GB, B2 paths, total runtime and cost estimate (this is the item 3 report).
   2. *Shared-instance check* before any stop: a process with cwd or arguments under `~/hrsd` (RD-Fusion; not `~/hrsd_occupants`), a tmux session not named for Baile Nua, any SSH login, or CPU above 1.5 cores over 5 min outside the `baile-nua-*` units. If any: email "[Baile Nua v1] complete, instance left running: <reason>", recheck hourly, give up after 24 h and email.
   3. *If clear:* email "[Baile Nua v1] stopping instance in 15 min"; after 15 min (activity re-checked over the last 5) run `sudo shutdown -h now`. Requires `ops/SHUTDOWN_BEHAVIOR_IS_STOP` (§3.5); without it, email and leave running. Never terminate.
   4. Clean-up of `~/hrsd_occupants/hrsd/work` stays Brian's decision; stopping deletes nothing.

## 11. Acceptance

- [ ] Secret scan clean (or exclusions listed)
- [ ] Engine digest matches; test suite matches the Mac
- [ ] Kill/resume byte-identical on the instance
- [ ] 13 segments DONE (warm-up + 2015–2026)
- [ ] Every year uploaded and `rclone check` clean
- [ ] PROVENANCE.md, release notes and known limitations uploaded
- [ ] Completion reported to Brian (COMPLETE email); instance stopped only by the auto-stop guard (§10.4), never terminated

## 12. Expected timing

Unknown until measured on the instance. The chain is serial, so speed depends on one core: on the Mac it ran at 80–165 s per simulated day. If the instance achieves 60–90 s/day, the run takes about 3–4.5 days. CC reports the measured rate after the first 30 days and a per-year ETA.
