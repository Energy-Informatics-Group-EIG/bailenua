#!/bin/bash
# notify.sh "<subject>" [body-file]   (body from stdin if no file)
# Sends one email with the "[Baile Nua v1]" prefix through ops/msmtprc and logs
# the subject (never the body or any credential) to ops/logs/alerts.log.
OPS=/home/ubuntu/hrsd_occupants/ops
TO=brianoregan78@gmail.com
SUBJ="[Baile Nua v1] $1"
[ "${NOTIFY_DRYRUN:-0}" = 1 ] && { echo "$(date -u "+%F %T")  DRYRUN  [Baile Nua v1] $1" >> "$OPS/logs/alerts.log"; cat > "$OPS/logs/dryrun_last_body.txt"; exit 0; }
BODY=$( [ -n "${2:-}" ] && cat "$2" || cat )
{
  printf 'From: Baile Nua v1 (EC2) <%s>\nTo: %s\nSubject: %s\nDate: %s\nContent-Type: text/plain; charset=UTF-8\n\n' \
    "$TO" "$TO" "$SUBJ" "$(date -R)"
  printf '%s\n\n-- \nsent by ~/hrsd_occupants/ops on %s (%s UTC)\n' "$BODY" "$(hostname)" "$(date -u '+%F %T')"
} | msmtp -C "$OPS/msmtprc" -a gmail "$TO"
rc=$?
echo "$(date -u '+%F %T')  rc=$rc  $SUBJ" >> "$OPS/logs/alerts.log"
exit $rc
