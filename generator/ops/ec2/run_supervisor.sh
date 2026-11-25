#!/bin/bash
# systemd entry point for baile-nua-v1.service (Linux counterpart of
# scripts/replay_launch.sh). exec so systemd supervises the python process
# directly; the per-year children stay in the unit's cgroup.
. /home/ubuntu/hrsd_occupants/ops/env.sh
cd "$HRSD/scripts" || exit 1
# Loop guard and post-pass recovery first; 78 = BLOCKED, which the unit's
# RestartPreventExitStatus=78 turns into a final stop (see pre_start.sh).
"$OPS/pre_start.sh"; rc=$?
[ $rc -eq 0 ] || exit $rc
echo "$(date '+%F %T') starting supervisor (engine $REPLAY_ENGINE_TAG, config $REPLAY_CONFIG)"
exec "$PY" -u replay_supervisor.py
