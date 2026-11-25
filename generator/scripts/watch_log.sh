#!/bin/bash
# Appends one watch tick to logs/watch.log. Digest-neutral: not under baile_nua.
L=/Users/brianoregan/hrsd/logs/watch.log
mkdir -p "$(dirname "$L")"
echo "$(date '+%Y-%m-%d') $(/Users/brianoregan/hrsd/scripts/watch_tick.sh)" >> "$L"
# Flag conditions worth a human look, on their own line.
T=$(tail -1 "$L")
S=$(echo "$T" | sed -n 's/.*swap \([0-9.]*\)%.*/\1/p')
M=$(echo "$T" | sed -n 's/.*mem free \([0-9.]*\)%.*/\1/p')
D=$(echo "$T" | sed -n 's/.*disk \([0-9]*\) GiB.*/\1/p')
R=$(echo "$T" | sed -n 's/.*RSS \([0-9]*\) MB.*/\1/p')
P=$(echo "$T" | sed -n 's/.*pid \(.*\)$/\1/p')
W=""
[ -f /Users/brianoregan/hrsd/status/BLOCKED.md ] && W="$W BLOCKED.md exists;"
[ "$P" = "NONE" ] && W="$W no --only child;"
awk -v s="${S:-0}" 'BEGIN{exit !(s>50)}' && W="$W swap >50%;"
awk -v m="${M:-100}" 'BEGIN{exit !(m<5)}'  && W="$W mem free <5%;"
[ "${D:-999}" -lt 30 ] 2>/dev/null && W="$W disk <30 GiB;"
[ "${R:-0}" -gt 16000 ] 2>/dev/null && W="$W RSS >16 GB;"
[ -n "$W" ] && echo "    ^^ ATTENTION:$W" >> "$L"
exit 0
