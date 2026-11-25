#!/bin/bash
# Emails status/MORNING.md after ops/morning.sh writes it (08:00 Irish time).
. /home/ubuntu/hrsd_occupants/ops/env.sh
"$OPS/notify.sh" "Morning report $(TZ=Europe/Dublin date '+%a %d %b')" "$HRSD/status/MORNING.md"
