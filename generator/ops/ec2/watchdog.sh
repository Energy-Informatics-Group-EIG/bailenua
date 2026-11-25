#!/bin/bash
# Watchdog, every 10 min from baile-nua-ops.service. Emails on:
#   * a new status/BLOCKED.md or status/UPLOAD_FAILED.md
#   * a service restart (systemd InvocationID changed)
#   * an attempt renamed aside by the supervisor's own in-process retry; if that
#     attempt had finished simulating, it is put back and only its post-pass is
#     re-run (stop, swap back, start -> pre_start.sh); a second failure of the
#     same segment stops the run (loop guard)
#   * no new simulated day for 30 min while simulating; during the post-run
#     phase (U27/export, no checkpoints by design) only after 3 h
#   * child RSS > 40 GB, swap use > 50 %, disk free < 40 GB
# Each condition alerts once when it starts, and re-arms when it clears.
. /home/ubuntu/hrsd_occupants/ops/env.sh
. "$OPS/lib.sh"
exec 8>"$STATE/watchdog.lock"; flock -n 8 || exit 0

once() {  # once <key> <subject> <body>: alert only if <key> was not raised yet
  [ -f "$STATE/raised.$1" ] && return
  touch "$STATE/raised.$1"; alert "$2" "$3"
}
clear_flag() { [ -f "$STATE/raised.$1" ] && { rm -f "$STATE/raised.$1"; event "cleared: $1"; }; }

# ---- files written by the run itself ----------------------------------------
for f in BLOCKED UPLOAD_FAILED; do
  p="$STATUS/$f.md"
  if [ -f "$p" ]; then once "$f.$(stat -c %Y "$p")" "$f: $(sed -n '3p' "$p" | cut -c1-80)" "$(cat "$p")"
  fi
done

# ---- service restarts -------------------------------------------------------
INV=$(systemctl show baile-nua-v1.service -p InvocationID --value)
NR=$(systemctl show baile-nua-v1.service -p NRestarts --value)
ACT=$(systemctl is-active baile-nua-v1.service)
LAST_INV=$(cat "$STATE/invocation_id" 2>/dev/null)
if [ -n "$INV" ] && [ "$INV" != "$LAST_INV" ]; then
  [ -n "$LAST_INV" ] && alert "service restarted (restart count $NR)" \
    "baile-nua-v1.service has a new invocation (now $ACT, NRestarts=$NR).
$(sudo -n journalctl -u baile-nua-v1.service -n 8 --no-pager -o short-iso 2>/dev/null)"
  echo "$INV" > "$STATE/invocation_id"
fi

SEG=$(current_segment)
if [ -z "$SEG" ]; then exit 0; fi
TOTAL=$(seg_days "$SEG")

# ---- attempts renamed aside (supervisor's in-process retries) ---------------
NP=$(n_partials "$SEG"); SEEN=$(cat "$STATE/$SEG.partials_seen" 2>/dev/null || echo 0)
if [ "$NP" -gt "$SEEN" ]; then
  echo "$NP" > "$STATE/$SEG.partials_seen"
  NEWEST=$(ls -d "$RUN/$SEG".partial.* | sort -t. -k3 -n | tail -1)
  ND=$(ls "$NEWEST/ckpt"/day_*.checkpoint.json.gz 2>/dev/null | wc -l)
  event "watchdog: $SEG has $NP attempt(s) renamed aside; newest $(basename "$NEWEST") at $ND/$TOTAL days"
  if [ "$ND" -eq "$TOTAL" ] && [ -f "$NEWEST/pkg/run_diagnostics.json" ] && [ ! -f "$STATE/$SEG.swapback_done" ]; then
    # The attempt finished simulating and died in its post-pass: put it back.
    touch "$STATE/$SEG.swapback_done"
    alert "$SEG: finished attempt renamed aside, restoring it" \
      "$(basename "$NEWEST") had all $TOTAL days simulated; the supervisor renamed it aside after a post-pass failure and started $SEG again from day 0. Stopping the service, moving the new attempt aside as $SEG.superseded.<ts> (kept), restoring the finished attempt, and restarting so only the post-pass runs."
    $SYSTEMCTL stop baile-nua-v1.service
    [ -d "$RUN/$SEG" ] && mv "$RUN/$SEG" "$RUN/$SEG.superseded.$(date +%s)"
    mv "$NEWEST" "$RUN/$SEG"
    echo $((NP - 1)) > "$STATE/$SEG.partials_seen"
    event "watchdog: restored $(basename "$NEWEST") as $SEG; starting service"
    $SYSTEMCTL start --no-block baile-nua-v1.service
    exit 0
  fi
  if [ "$NP" -ge 2 ]; then
    block "$SEG" "$NP attempts have now failed (latest renamed aside at day $ND of $TOTAL). Loop guard."
    exit 0
  fi
  alert "$SEG: attempt renamed aside at day $ND/$TOTAL" "The supervisor retried $SEG in-process (D-135: renamed aside, re-run from the previous segment's final checkpoint). Failure $NP of 2 for $SEG."
fi

# ---- progress stall ---------------------------------------------------------
if [ "$ACT" = active ] && [ -d "$RUN/$SEG" ]; then
  LAST=$(ls -t "$RUN/$SEG/ckpt"/day_*.checkpoint.json.gz 2>/dev/null | head -1)
  REF=${LAST:-$RUN/$SEG}
  AGE=$(( $(date +%s) - $(stat -c %Y "$REF") ))
  ND=$(ls "$RUN/$SEG/ckpt"/day_*.checkpoint.json.gz 2>/dev/null | wc -l)
  if [ "$ND" -lt "$TOTAL" ]; then LIMIT=1800; PHASE="simulating (day $ND/$TOTAL)"
  else LIMIT=10800; PHASE="post-run phase (U27/export), all $TOTAL days simulated"; fi
  KEY="stall.$SEG.$(basename "$REF")"
  if [ "$AGE" -gt "$LIMIT" ]; then
    once "$KEY" "$SEG: no progress for $((AGE / 60)) min" "No new checkpoint for $((AGE / 60)) min; $PHASE. Service is $ACT."
  fi
fi

# ---- resources --------------------------------------------------------------
PID=$(pgrep -f '[r]eplay_supervisor.py --only' | head -1)
RSS=$([ -n "$PID" ] && awk '/VmRSS/{printf "%d", $2/1048576}' "/proc/$PID/status" 2>/dev/null || echo 0)
SWP=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{printf "%d", t?100*(t-f)/t:0}' /proc/meminfo)
DISK=$(df -BG --output=avail "$HRSD" | tail -1 | tr -dc 0-9)
[ "${RSS:-0}" -gt 40 ] && once rss "RSS over 40 GB ($RSS GB) in $SEG" "Child RSS $RSS GB (MemoryHigh 52G; swap use $SWP%). Expected during each year's U27 step."
[ "${RSS:-0}" -lt 35 ] && clear_flag rss
[ "$SWP" -gt 50 ] && once swap "swap use over 50% ($SWP%)" "Swap use $SWP% of 96 GB during $SEG; child RSS $RSS GB."
[ "$SWP" -lt 40 ] && clear_flag swap
[ "${DISK:-999}" -lt 40 ] && once disk "disk free under 40 GB ($DISK GB)" "Free on /: $DISK GB."
[ "${DISK:-0}" -gt 45 ] && clear_flag disk
exit 0
