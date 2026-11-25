#!/bin/bash
# The loop guard and post-pass recovery, run by ops/run_supervisor.sh (the
# unit's ExecStart) before it execs the supervisor; that includes each
# automatic restart after a crash.
#
# Exit 0: go ahead and start the supervisor. Exit 78: BLOCKED, do not start.
# 78 must come from ExecStart, not ExecStartPre: the unit has
# RestartPreventExitStatus=78, which systemd ignores for ExecStartPre failures,
# and ConditionPathExists=!BLOCKED.md is not re-checked on automatic restarts
# (both tested on this host on a throwaway unit, 2026-10-17). So a BLOCKED exit
# from ExecStartPre looped every RestartSec.
#
# If the current segment's directory exists without DONE.json, the previous
# supervisor ended mid-segment (crash, OOM kill, reboot or manual stop):
#   * simulation finished, post-pass did not -> finish only the post-pass
#     (ops/finish_segment.py); DONE.json is written, the supervisor skips the year
#   * otherwise -> the supervisor's D-135 behaviour: rename aside, re-run the
#     segment from the previous segment's final checkpoint. (A mid-year resume
#     is not possible from outside the engine; see ops/README.md.)
# Loop guard: if the same segment has now failed twice (attempts renamed aside
# + this dead attempt + failed post-pass recoveries), write BLOCKED.md, alert,
# and exit 78.
. /home/ubuntu/hrsd_occupants/ops/env.sh
. "$OPS/lib.sh"
cd "$HRSD/scripts" || exit 1

if [ -f "$STATUS/BLOCKED.md" ]; then
  event "pre_start: BLOCKED.md exists, not starting (exit 78)"
  exit 78
fi

SEG=$(current_segment)
[ -z "$SEG" ] && { event "pre_start: all segments DONE"; exit 0; }
[ -d "$RUN/$SEG" ] || { event "pre_start: $SEG not started yet, clean start"; exit 0; }

DAYS=$(ls "$RUN/$SEG/ckpt"/day_*.checkpoint.json.gz 2>/dev/null | wc -l)
TOTAL=$(seg_days "$SEG")
FF=$(cat "$STATE/$SEG.finish_failures" 2>/dev/null || echo 0)
FAILS=$(( $(n_partials "$SEG") + 1 + FF ))
event "pre_start: $SEG attempt ended without DONE at $DAYS/$TOTAL days; failures for $SEG now $FAILS"

if NO_STOP=1 "$PY" "$OPS/finish_segment.py" "$SEG" --check >> "$OPS/logs/ops_events.log" 2>&1; then
  alert "$SEG: post-pass recovery started" "The $SEG simulation finished ($DAYS/$TOTAL days, chain verified) but the supervisor ended in the post-run phase. Running only the post-pass (U27, export, checks) - the year is not re-simulated."
  if "$PY" -u "$OPS/finish_segment.py" "$SEG" > "$OPS/logs/finish_$SEG.log" 2>&1; then
    alert "$SEG: post-pass recovered, DONE" "$(tail -3 "$OPS/logs/finish_$SEG.log")"
    exit 0
  fi
  echo $((FF + 1)) > "$STATE/$SEG.finish_failures"
  NO_STOP=1 block "$SEG" "post-pass recovery failed after the simulation completed (see ~/hrsd_occupants/ops/logs/finish_$SEG.log): $(tail -1 "$OPS/logs/finish_$SEG.log" | cut -c1-300)"
  exit 78
fi

if [ "$FAILS" -ge 2 ]; then
  NO_STOP=1 block "$SEG" "failed $FAILS times (last attempt ended at day $DAYS of $TOTAL). Loop guard: not starting another attempt."
  exit 78
fi
alert "$SEG: attempt ended at day $DAYS/$TOTAL, restarting" "The supervisor ended during the $SEG simulation (day $DAYS of $TOTAL). It restarts now and, per D-135, renames the attempt aside and re-runs $SEG from the previous segment's final checkpoint. This is failure $FAILS of 2 for $SEG; a second failure stops the run."
exit 0
