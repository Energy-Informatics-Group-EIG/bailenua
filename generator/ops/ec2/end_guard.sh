#!/bin/bash
# Auto-stop guard for the end of v1.        end_guard.sh tick|final [--dry-run]
#
# tick  (every 10 min, last step of baile-nua-ops.service):
#   1. complete? 13 DONE; 12 years UPLOADED with rclone check clean; PROVENANCE.md,
#      RELEASE_NOTES_v1.md, V1_KNOWN_LIMITATIONS.md on v1/docs/ and checked; then a
#      final full rclone check of v1/ against local. -> "[Baile Nua v1] COMPLETE" (once)
#   2. shared-instance safety: RD-Fusion processes (cwd/args under ~/hrsd), tmux
#      sessions other than Baile Nua's, SSH logins, other CPU > 1.5 cores over 5 min.
#      Busy -> email "complete, instance left running: <reason>", recheck hourly,
#      give up (email) after 24 h.
#   3. clear -> email "stopping instance in 15 min" and schedule `final` (+10 min).
# final: NO_STOP? stop-behaviour confirmed? still clear over a 5-min CPU sample
#   (ending ~15 min after the warning)? -> sudo shutdown -h now. Never terminates.
# Disabled whenever ops/NO_STOP exists. --dry-run: no email, no timer, no shutdown.
. /home/ubuntu/hrsd_occupants/ops/env.sh
. "$OPS/lib.sh"
MODE=${1:-tick}; DRY=0; [ "${2:-}" = --dry-run ] || [ "${1:-}" = --dry-run ] && DRY=1
[ "$1" = --dry-run ] && MODE=tick
[ $DRY = 1 ] && export NOTIFY_DRYRUN=1
G="$STATE/endguard"; mkdir -p "$G"
NO_STOP_FILE="${NO_STOP_FILE:-$OPS/NO_STOP}"
CONFIRM_FILE="${CONFIRM_FILE:-$OPS/SHUTDOWN_BEHAVIOR_IS_STOP}"
PRICE_LOW=0.61; PRICE_HIGH=0.70   # US$/h on-demand r7a.2xlarge eu-west-1: estimate, not checked against AWS
LABEL=$MODE; [ $DRY = 1 ] && LABEL="$MODE dry-run"
say() { event "end_guard[$LABEL]: $*"; [ $DRY = 1 ] && echo "  $*"; return 0; }
YEARS="2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026"
DOCS="PROVENANCE.md RELEASE_NOTES_v1.md V1_KNOWN_LIMITATIONS.md"
DOCS_LOCAL="${DOCS_LOCAL:-$HRSD/docs}"
NOW=$(date +%s)

rc() {  # rclone with the B2 key loaded; RCLONE_STUB=1 in tests
  [ "${RCLONE_STUB:-0}" = 1 ] && return 0
  ( set -a; . "$B2_ENV_FILE"; set +a; rclone "$@" ) >> "$OPS/logs/end_guard_rclone.log" 2>&1
}

# ---- 1. completion ------------------------------------------------------------
not_complete() {  # prints the first unmet condition; empty when every cheap check holds
  local s n=0
  for s in $SEGMENTS; do [ -f "$RUN/$s/DONE.json" ] && n=$((n + 1)); done
  [ $n -eq 13 ] || { echo "$n of 13 segments DONE"; return; }
  for s in $YEARS; do
    "$PY" -I -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if str(d.get("rclone_check","")).startswith("0 differences") else 1)' \
      "$STATE/$s.UPLOADED.json" 2>/dev/null || { echo "$s not uploaded and checked"; return; }
  done
  for f in $DOCS; do [ -f "$DOCS_LOCAL/$f" ] || { echo "local docs/$f missing"; return; }; done
  rc check --one-way "$DOCS_LOCAL" "$B2_DEST/docs/" $(for f in $DOCS; do printf -- '--include %s ' "$f"; done) \
    || { echo "v1/docs/ not uploaded or rclone check not clean"; return; }
}

full_check() {  # the final full rclone check of v1/ against local
  local s top want
  if [ "${RCLONE_STUB:-0}" != 1 ]; then
    top=$( ( set -a; . "$B2_ENV_FILE"; set +a; rclone lsf --dirs-only "$B2_DEST/" ) 2>/dev/null | tr -d / | sort | paste -sd' ')
    want=$(printf '%s\n' $YEARS docs | sort | paste -sd' ')
    [ "$top" = "$want" ] || { echo "v1/ top level is [$top], expected [$want]"; return 1; }
  fi
  for s in $YEARS; do
    if [ -f "$STATE/$s.parquet.sha1" ]; then
      # Local Parquet pruned after a clean one-way check (2026-10-18): the rest of
      # pkg two-way as usual, the Parquet on B2 against the SHA-1 list saved first.
      rc check "$RUN/$s/pkg" "$B2_DEST/$s/" --exclude '_segment/**' --exclude '*.parquet' || { echo "v1/$s/ differs from local pkg (non-Parquet)"; return 1; }
      rc checksum sha1 "$STATE/$s.parquet.sha1" "$B2_DEST/$s/" --include '*.parquet' || { echo "v1/$s/ Parquet differs from state/$s.parquet.sha1"; return 1; }
    else
      rc check "$RUN/$s/pkg" "$B2_DEST/$s/" --exclude '_segment/**' || { echo "v1/$s/ differs from local pkg"; return 1; }
    fi
    rc check "$STATE/meta/$s" "$B2_DEST/$s/_segment/" || { echo "v1/$s/_segment/ differs from local"; return 1; }
  done
  rc check --one-way "$DOCS_LOCAL" "$B2_DEST/docs/" $(for f in $DOCS; do printf -- '--include %s ' "$f"; done) \
    || { echo "v1/docs/ differs"; return 1; }
}

complete_email() {
  "$PY" -I - "$RUN" "$STATE" "$PRICE_LOW" "$PRICE_HIGH" "$B2_DEST" <<'PY' | "$OPS/notify.sh" "COMPLETE"
import json, sys, re, datetime as dt
run, state, lo, hi, dest = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
tr = tb = 0
print("v1 is complete: 13 segments DONE, every year uploaded, docs uploaded, final full rclone check of v1/ clean.\n")
print(f"{'year':<6}{'rows':>15}{'GB':>8}{'wall h':>8}  B2 path")
for y in range(2015, 2027):
    d = json.load(open(f"{run}/{y}/DONE.json")); u = json.load(open(f"{state}/{y}.UPLOADED.json"))
    r = sum((d.get("row_counts") or {}).values()); tr += r; tb += u["remote_bytes"]
    print(f"{y:<6}{r:>15,}{u['remote_bytes']/1e9:>8.2f}{d.get('wall_h'):>8}  {u['dest']}")
print(f"{'total':<6}{tr:>15,}{tb/1e9:>8.2f}")
first = re.match(r"(\S+ \S+)", open(f"{run}/children.log").readline()).group(1)
t0 = dt.datetime.strptime(first, "%Y-%m-%d %H:%M:%S"); h = (dt.datetime.now() - t0).total_seconds() / 3600
print(f"\nRun wall-clock: {first} to now = {h:.1f} h (includes restarts and post-passes).")
print(f"Compute cost estimate: {h:.1f} h x US${lo:.2f}-{hi:.2f}/h = US${h*lo:,.2f}-{h*hi:,.2f}")
print("(on-demand r7a.2xlarge eu-west-1, my estimate; EBS and B2 storage not included).")
print(f"Docs: {dest}/docs/ (PROVENANCE.md, RELEASE_NOTES_v1.md, V1_KNOWN_LIMITATIONS.md).")
PY
}

# ---- 2. shared-instance activity -------------------------------------------------
activity() {  # prints reasons, one per line; empty = clear. FAKE_ACTIVITY overrides in tests.
  if [ -n "${FAKE_ACTIVITY+x}" ]; then [ -n "$FAKE_ACTIVITY" ] && echo "$FAKE_ACTIVITY"; return; fi
  "$PY" -I - $$ <<'PY'
import os, re, sys
me = {int(sys.argv[1]), os.getpid(), os.getppid()}
HOME_HRSD = re.compile(r"(^|[\s=:'\"])(/home/ubuntu/hrsd|~/hrsd)(/|[\s'\"]|$)")
hits = []
for p in os.listdir("/proc"):
    if not p.isdigit() or int(p) in me: continue
    try:
        cwd = os.readlink(f"/proc/{p}/cwd")
        args = open(f"/proc/{p}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        continue
    if re.match(r"^/home/ubuntu/hrsd(/|$)", cwd) or HOME_HRSD.search(" " + args):
        hits.append(f"pid {p} ({args.split(' ')[0].rsplit('/',1)[-1] or '?'}) cwd={cwd}")
if hits:
    print(f"RD-Fusion process(es) under ~/hrsd: {len(hits)}, e.g. " + "; ".join(hits[:3]))
PY
  local sock s others=""
  for sock in $(sudo -n find /tmp -maxdepth 2 -path '/tmp/tmux-*' -type s 2>/dev/null); do
    for s in $(sudo -n tmux -S "$sock" ls -F '#S' 2>/dev/null); do
      echo "$s" | grep -qiE 'baile|occupants' || others="$others $s"
    done
  done
  [ -n "$others" ] && echo "tmux session(s) other than Baile Nua's:$others"
  local ssh; ssh=$(who | awk '$NF !~ /^\(tmux/ {printf "%s %s %s; ", $1, $2, $NF}')
  [ -n "$ssh" ] && echo "SSH login(s): $ssh"
  # CPU used outside the baile-nua-* units, cores-equivalent over 5 min.
  local cg=/sys/fs/cgroup/system.slice b0 u0 b1 u1
  ours() { cat $cg/baile-nua-*.service/cpu.stat 2>/dev/null | awk '/^usage_usec/{s+=$2} END{print s+0}'; }
  busy() { awk '/^cpu /{print ($2+$3+$4+$7+$8+$9)*10000}' /proc/stat; }   # jiffies(1/100 s) -> usec
  b0=$(busy); u0=$(ours); sleep "${CPU_SAMPLE_S:-300}"; b1=$(busy); u1=$(ours)
  awk -v b=$((b1 - b0)) -v u=$((u1 - u0)) -v t="${CPU_SAMPLE_S:-300}" \
    'BEGIN{c=(b-u)/1e6/t; if (c>1.5) printf "CPU outside Baile Nua %.2f cores over %d s (> 1.5)\n", c, t}'
}

# ---- main --------------------------------------------------------------------------
if [ -f "$NO_STOP_FILE" ]; then
  say "disabled: $NO_STOP_FILE exists"
  [ "$MODE" = final ] && [ ! -f "$G/cancel_sent" ] && { touch "$G/cancel_sent"; alert "auto-stop cancelled (NO_STOP)" "$NO_STOP_FILE exists; the instance is left running."; }
  exit 0
fi
[ -f "$G/gave_up" ] && exit 0

if [ "$MODE" = tick ]; then
  [ -f "$G/stop_scheduled" ] && { say "stop already scheduled"; exit 0; }
  if [ ! -f "$G/complete_verified" ]; then
    why=$(not_complete); [ -n "$why" ] && { say "not complete: $why"; exit 0; }
    say "cheap completion checks pass; running final full rclone check of v1/"
    if ! why=$(full_check); then say "final check NOT clean: $why"; alert "final rclone check of v1/ not clean" "$why"; exit 0; fi
    touch "$G/complete_verified"; say "final full check clean"
    [ -f "$G/complete_sent" ] || { complete_email && touch "$G/complete_sent"; }
  fi
  # hourly cadence once the instance has been found busy
  if [ -f "$G/busy_first" ] && [ $((NOW - $(cat "$G/busy_last"))) -lt 3600 ]; then say "busy earlier; next recheck within the hour"; exit 0; fi
  reasons=$(activity)
  if [ -n "$reasons" ]; then
    [ -f "$G/busy_first" ] || { echo "$NOW" > "$G/busy_first"; alert "complete, instance left running: $(echo "$reasons" | head -1 | cut -c1-90)" "Not stopping: the instance is in use.
$reasons

Rechecking hourly for up to 24 h. Cancel the auto-stop with: touch $NO_STOP_FILE"; }
    echo "$NOW" > "$G/busy_last"
    say "busy: $(echo "$reasons" | paste -sd'|')"
    if [ $((NOW - $(cat "$G/busy_first"))) -ge 86400 ]; then
      touch "$G/gave_up"
      alert "auto-stop given up after 24 h, instance left running" "Still in use after 24 hourly checks:
$reasons
The guard will not try again. Stop the instance yourself when it is free."
    fi
    exit 0
  fi
  say "clear: scheduling shutdown"
  alert "stopping instance in 15 min" "v1 is complete and the instance looks idle (no ~/hrsd processes, no other tmux, no SSH logins, other CPU <= 1.5 cores).
It will be shut down (stopped, not terminated) at about $(date -d '+15 min' '+%H:%M %Z').
To cancel: touch $NO_STOP_FILE"
  echo "$NOW" > "$G/stop_scheduled"
  if [ $DRY = 1 ]; then echo "  would run: sudo systemd-run --on-active=600 --unit=baile-nua-autostop --uid=ubuntu $OPS/end_guard.sh final"
  else sudo -n systemd-run --on-active=600 --unit=baile-nua-autostop --uid=ubuntu "$OPS/end_guard.sh" final >> "$OPS/logs/ops_events.log" 2>&1; fi
  exit 0
fi

if [ "$MODE" = final ]; then
  if [ ! -f "$G/complete_verified" ] || [ ! -f "$G/stop_scheduled" ]; then
    say "refusing: final without a verified completion and a scheduled stop"; exit 1
  fi
  if [ ! -f "$CONFIRM_FILE" ]; then
    touch "$G/gave_up"; say "no shutdown: $CONFIRM_FILE missing"
    alert "complete, instance left running: shutdown behaviour not confirmed" "The guard cannot see the instance's shutdown behaviour (no AWS CLI or IAM role), and an OS shutdown TERMINATES an instance whose behaviour is 'terminate'. Not shutting down. If the console shows 'Stop', create $CONFIRM_FILE for future runs."
    exit 0
  fi
  reasons=$(activity)   # includes the 5-min CPU sample, ending ~15 min after the warning
  if [ -n "$reasons" ]; then
    rm -f "$G/stop_scheduled"; echo "$NOW" > "$G/busy_last"; [ -f "$G/busy_first" ] || echo "$NOW" > "$G/busy_first"
    say "activity appeared before shutdown: $(echo "$reasons" | paste -sd'|')"
    alert "complete, instance left running: $(echo "$reasons" | head -1 | cut -c1-90)" "Activity appeared during the 15-minute warning:
$reasons
Shutdown cancelled; rechecking hourly for up to 24 h."
    exit 0
  fi
  say "shutting down now"
  if [ $DRY = 1 ]; then echo "  would run: sudo shutdown -h now"; else touch "$G/stopped"; sudo -n shutdown -h now; fi
fi
