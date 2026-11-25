# Shared helpers for the ops scripts. Source after env.sh.
STATE="${STATE:-$OPS/state}"; mkdir -p "$STATE" "$OPS/logs"
SYSTEMCTL="${SYSTEMCTL:-sudo -n systemctl}"   # tests set SYSTEMCTL=echo

alert() {  # alert "<subject>" "<body>"  - email, and a line in ops/logs/ops_events.log
  echo "$(date -u '+%F %T')  ALERT  $1" >> "$OPS/logs/ops_events.log"
  printf '%s\n\nHost status:\n%s\n%s\n' "$2" "$(cat "$STATUS/LAST.txt" 2>/dev/null)" \
    "$(cat "$STATUS/HOST.txt" 2>/dev/null)" | "$OPS/notify.sh" "$1" || true
}

event() { echo "$(date -u '+%F %T')  $*" >> "$OPS/logs/ops_events.log"; }

# First segment (config order) without DONE.json, or empty when all are done.
current_segment() {
  local s; for s in $SEGMENTS; do [ -f "$RUN/$s/DONE.json" ] || { echo "$s"; return; }; done
}

seg_days() {  # days in a segment, from the config
  "$PY" -I -c 'import json,sys,datetime as d
c=json.load(open(sys.argv[1]))
s=next(x for x in c["segments"] if x["name"]==sys.argv[2])
print((d.date.fromisoformat(s["end"])-d.date.fromisoformat(s["start"])).days+1)' \
    "$HRSD/scripts/$REPLAY_CONFIG" "$1"
}

n_partials() { ls -d "$RUN/$1".partial.* 2>/dev/null | wc -l; }

block() {  # block "<segment>" "<reason>"  - BLOCKED.md, stop the service, alert
  local seg=$1 why=$2
  if [ ! -f "$STATUS/BLOCKED.md" ]; then
    cat > "$STATUS/BLOCKED.md" <<EOF
# BLOCKED — $(date '+%F %T')

Segment **$seg**: $why

Written by \`~/hrsd_occupants/ops\` (loop guard). \`baile-nua-v1.service\` is
stopped and will not start while this file exists. Nothing was deleted: every
attempt is kept as \`work/replay_2015_2026/$seg.partial.*\` (D-135).
To resume after fixing the cause: remove this file, then
\`sudo systemctl start baile-nua-v1\`.
EOF
  fi
  event "BLOCKED $seg: $why"
  alert "BLOCKED: $seg — run stopped" "Segment $seg: $why

The service is stopped and stays stopped until status/BLOCKED.md is removed.
Partial attempts kept: $(n_partials "$seg") (renamed aside, never deleted)."
  [ "${NO_STOP:-0}" = 1 ] || $SYSTEMCTL stop --no-block baile-nua-v1.service
}
