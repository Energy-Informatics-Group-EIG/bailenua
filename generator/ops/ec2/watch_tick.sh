#!/bin/bash
# Linux counterpart of scripts/watch_tick.sh + watch_log.sh. Every 10 min:
# appends one line to hrsd/logs/watch.log (read by the 08:00 morning report)
# and rewrites hrsd/status/HOST.txt. Touches only the live segment's ckpt dir
# and small status files, never a tree walk (D-151).
. /home/ubuntu/hrsd_occupants/ops/env.sh
SEG=$(awk '{print $3}' "$HRSD/status/LAST.txt" 2>/dev/null)
[ -d "$RUN/$SEG/ckpt" ] || SEG=$(ls "$RUN" 2>/dev/null | grep -E '^(warmup_2014|20[0-9][0-9])$' | sort -V | tail -1)
CK="$RUN/$SEG/ckpt"

MEMAV=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf "%.1f", 100*a/t}' /proc/meminfo)
SWAP=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{printf "%.1f", t?100*(t-f)/t:0}' /proc/meminfo)
DISK=$(df -BG --output=avail "$HRSD" | tail -1 | tr -dc 0-9)
PID=$(pgrep -f '[r]eplay_supervisor.py --only' | head -1)
RSS=$([ -n "$PID" ] && awk '/VmRSS/{printf "%.0f", $2/1024}' /proc/$PID/status 2>/dev/null || echo 0)

read DAY NDAY RATE STALLS <<<"$(stat -c '%Y %n' "$CK"/day_*.checkpoint.json.gz 2>/dev/null | sort -n | awk '
  {t[NR]=$1; n=$2} END{
    if(NR==0){print "- 0 0 0"; exit}
    sub(/.*day_0*/,"",n); sub(/\..*/,"",n)
    m=0; k=0; for(i=2;i<=NR;i++){g[++k]=t[i]-t[i-1]}
    if(k>0){ asort(g, s); med=(k%2)?s[int(k/2)+1]:(s[k/2]+s[k/2+1])/2
      for(i=1;i<=k;i++){ if(g[i]>2*med) st++; else {sum+=g[i]; c++} } }
    printf "%d %d %.0f %d", n+0, NR, (NR>1?(t[NR]-t[1])/(NR-1):0), st+0 }')"
# Attempts of this segment thrown away by a restart (renamed aside, never deleted).
ASIDE=$(ls -d "$RUN/$SEG".partial.* 2>/dev/null | wc -l)

LINE="$(date '+%F %H:%M')  sim_day $DAY ($SEG d$NDAY)  swap $SWAP%  mem avail $MEMAV%  disk $DISK GiB  $RATE s/day all-in this attempt (incl $STALLS flush stall(s))  restarts $ASIDE  RSS $RSS MB  pid ${PID:-NONE}"
echo "$LINE" >> "$HRSD/logs/watch.log"
W=""
[ -f "$HRSD/status/BLOCKED.md" ] && W="$W BLOCKED.md exists;"
[ -f "$HRSD/status/UPLOAD_FAILED.md" ] && W="$W UPLOAD_FAILED.md exists;"
[ -z "$PID" ] && ! grep -q 'ALL SEGMENTS DONE' "$HRSD/status/LAST.txt" 2>/dev/null && W="$W no --only child;"
[ "${DISK:-999}" -lt 30 ] && W="$W disk <30 GiB;"
[ "${RSS:-0}" -gt 16384 ] && W="$W RSS >16 GB (warning; gate is the config's rss_gate_mb);"
awk -v m="$MEMAV" 'BEGIN{exit !(m<10)}' && W="$W mem avail <10%;"
[ -n "$W" ] && echo "    ^^ ATTENTION:$W" >> "$HRSD/logs/watch.log"
{ echo "$LINE"; [ -n "$W" ] && echo "ATTENTION:$W"
  echo "service: $(systemctl is-active baile-nua-v1.service 2>/dev/null)"; } > "$HRSD/status/HOST.txt"
exit 0
