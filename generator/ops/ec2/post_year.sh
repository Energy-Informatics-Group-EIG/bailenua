#!/bin/bash
# Per-year post-pass on top of the supervisor (spec §6-§7). Run every 10 min by
# baile-nua-ops.timer; idempotent, one instance at a time.
#
# The supervisor already does the export post-pass and its secret/personal scan
# before it writes DONE.json. For every segment with DONE.json this adds:
#   1. scripts/verify_segment.py               (fail x3 -> BLOCKED, run stopped)
#   2. a scan for the B2 key in the package     (hit     -> BLOCKED, run stopped)
#   3. rclone copy --checksum to $B2_DEST/<year>/, segment metadata to _segment/
#   4. rclone check --one-way, 0 differences required, then UPLOADED marker
# Upload failures (x3) write status/UPLOAD_FAILED.md and are retried next tick:
# the packages are local and intact, so a network fault does not stop the run.
# The warm-up is verified but never uploaded (its output is discarded by design).
# Markers live in ops/state, never in the run's output tree.
. /home/ubuntu/hrsd_occupants/ops/env.sh
STATE="${STATE:-$OPS/state}"; LOGS="${LOGS:-$OPS/logs}"; mkdir -p "$STATE" "$LOGS"
exec 9>"$STATE/post_year.lock"; flock -n 9 || exit 0
LOG="$LOGS/post_year.log"
say() { echo "$(date '+%F %T')  $*" >> "$LOG"; }

block() {  # $1 segment, $2 reason
  [ -f "$HRSD/status/BLOCKED.md" ] || cat > "$HRSD/status/BLOCKED.md" <<EOF
# BLOCKED — $(date '+%F %T')

Post-year check for segment **$1** failed: $2

Written by \`~/hrsd_occupants/ops/post_year.sh\`, which then stopped
\`baile-nua-v1.service\`. Nothing was deleted. See \`~/hrsd_occupants/ops/logs/\`.
Remove this file and \`sudo systemctl start baile-nua-v1\` to resume; completed
segments are skipped by their DONE sentinels.
EOF
  say "BLOCKED $1: $2"
  sudo -n systemctl stop baile-nua-v1.service >> "$LOG" 2>&1
  OPS_STATE_SAVE=$STATE; . "$OPS/lib.sh"; STATE=$OPS_STATE_SAVE
  alert "BLOCKED: $1 — post-year check failed, run stopped" "Segment $1: $2"
}

year_email() {  # email one delivered year: rows, GB, rclone check
  "$PY" -I - "$1" "$RUN" "$STATE" <<'PY' | "$OPS/notify.sh" "$1 uploaded to B2"
import json, sys
seg, run, state = sys.argv[1:4]
d = json.load(open(f"{run}/{seg}/DONE.json")); u = json.load(open(f"{state}/{seg}.UPLOADED.json"))
rows = d.get("row_counts") or {}
print(f"Year {seg} is verified and uploaded.\n")
print(f"  B2 path        {u['dest']}")
print(f"  rows           {sum(rows.values()):,} across {len(rows)} datasets")
print(f"  size on B2     {u['remote_bytes']/1e9:.2f} GB in {u['remote_objects']} objects")
print(f"  rclone check   {u['rclone_check']}")
print(f"  wall           {d.get('wall_h')} h ({d.get('s_per_day')} s/day), peak RSS {d.get('peak_rss_mb')} MB")
print(f"  export         {d.get('export_written')} written, {d.get('export_failed')} failed")
print("\nRows per dataset:")
for k in sorted(rows): print(f"  {k:<5} {rows[k]:>14,}")
PY
}

key_scan() {  # exit 1 if either B2 key string appears in a text file of the segment
  ( set -a; . "$B2_ENV_FILE"; set +a
    "$PY" -I - "$1" <<'PY'
import os, sys, pathlib
needles = [os.environ[k].encode() for k in ("B2_KEY_ID", "B2_APP_KEY") if os.environ.get(k)]
hits = 0
for p in pathlib.Path(sys.argv[1]).rglob("*"):
    if p.is_file() and p.suffix in (".json", ".md", ".txt", ".csv", ".log", ".yaml", ".yml"):
        b = p.read_bytes()
        hits += any(n in b for n in needles)
print(f"key scan: {hits} file(s) with a B2 key string")
sys.exit(1 if hits else 0)
PY
  )
}

upload() {  # $1 segment; returns 0 only when rclone check is clean for both trees
  local seg=$1 dir="$RUN/$1" meta="$STATE/meta/$1"
  rm -rf "$meta"; mkdir -p "$meta"
  for f in DONE.json ENGINE.json export_report.json; do [ -f "$dir/$f" ] && cp "$dir/$f" "$meta/"; done
  cp "$RUN/RUN_DIGESTS.json" "$meta/" 2>/dev/null
  cp "$LOGS/verify_$seg.log" "$meta/verify_segment.log"
  ( set -a; . "$B2_ENV_FILE"; set +a
    rclone copy --checksum --transfers 16 --log-level NOTICE "$dir/pkg" "$B2_DEST/$seg/" &&
    rclone copy --checksum --log-level NOTICE "$meta" "$B2_DEST/$seg/_segment/" &&
    rclone check --one-way "$dir/pkg" "$B2_DEST/$seg/" --exclude '_segment/**' &&
    rclone check --one-way "$meta" "$B2_DEST/$seg/_segment/" &&
    rclone size --json "$B2_DEST/$seg/" > "$STATE/$seg.remote_size.json"
  ) >> "$LOGS/upload_$seg.log" 2>&1
}

for seg in $SEGMENTS; do
  dir="$RUN/$seg"
  [ -f "$dir/DONE.json" ] || continue
  [ -f "$STATE/$seg.UPLOADED.json" ] && continue
  [ "$seg" = warmup_2014 ] && [ -f "$STATE/$seg.VERIFIED.json" ] && continue

  if [ ! -f "$STATE/$seg.VERIFIED.json" ]; then
    ok=0
    for a in 1 2 3; do
      say "$seg verify_segment attempt $a"
      (cd "$HRSD/scripts" && "$PY" -u verify_segment.py "$dir") > "$LOGS/verify_$seg.log" 2>&1 && { ok=1; break; }
      sleep 30
    done
    [ $ok = 1 ] || { block "$seg" "verify_segment.py failed 3 times (ops/logs/verify_$seg.log)"; exit 1; }
    if [ "$seg" != warmup_2014 ]; then
      key_scan "$dir" >> "$LOG" 2>&1 || { block "$seg" "a B2 key string was found in the segment's files"; exit 1; }
    fi
    echo "{\"segment\": \"$seg\", \"verified\": \"$(date '+%F %T')\"}" > "$STATE/$seg.VERIFIED.json"
    say "$seg verified"
  fi
  [ "$seg" = warmup_2014 ] && continue

  ok=0
  for a in 1 2 3; do
    say "$seg upload attempt $a"
    upload "$seg" && { ok=1; break; }
    sleep 60
  done
  if [ $ok = 1 ]; then
    "$PY" -I - "$seg" "$STATE" "$B2_DEST" <<'PY'
import json, sys, datetime
seg, state, dest = sys.argv[1:4]
size = json.load(open(f"{state}/{seg}.remote_size.json"))
json.dump({"segment": seg, "uploaded": datetime.datetime.now().isoformat(timespec="seconds"),
           "dest": f"{dest}/{seg}/", "remote_objects": size.get("count"),
           "remote_bytes": size.get("bytes"), "rclone_check": "0 differences (one-way, pkg and _segment)"},
          open(f"{state}/{seg}.UPLOADED.json", "w"), indent=2)
PY
    rm -f "$HRSD/status/UPLOAD_FAILED.md"
    say "$seg UPLOADED"
    year_email "$seg" && say "$seg upload email sent" || say "$seg upload email FAILED"
  else
    echo "# Upload failed — $(date '+%F %T')

Segment **$seg** failed upload/check 3 times; retried every 10 min. The local
package is intact. Log: \`~/hrsd_occupants/ops/logs/upload_$seg.log\`." > "$HRSD/status/UPLOAD_FAILED.md"
    say "$seg upload FAILED x3, will retry"
  fi
done

# status/UPLOADS.md: one line per delivered year
{
  echo "# B2 uploads — $(date '+%F %T')"; echo
  echo "Destination \`$B2_DEST/<year>/\`. Written by \`~/hrsd_occupants/ops/post_year.sh\`."; echo
  echo "| segment | verified | uploaded | objects | GB |"; echo "|---|---|---|---|---|"
  for seg in $SEGMENTS; do
    v=$([ -f "$STATE/$seg.VERIFIED.json" ] && echo yes || echo —)
    if [ -f "$STATE/$seg.UPLOADED.json" ]; then
      "$PY" -I -c 'import json,sys;d=json.load(open(sys.argv[1]));print("| %s | yes | %s | %s | %.2f |" % (d["segment"], d["uploaded"], d["remote_objects"], d["remote_bytes"]/1e9))' "$STATE/$seg.UPLOADED.json"
    else
      u=$([ "$seg" = warmup_2014 ] && echo "n/a (discarded)" || echo —)
      echo "| $seg | $v | $u | | |"
    fi
  done
} > "$HRSD/status/UPLOADS.md"

# Completion (COMPLETE email, auto-stop) is handled by ops/end_guard.sh.
