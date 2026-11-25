#!/bin/bash
# launchd entry point. `exec` so caffeinate replaces this shell and launchd
# supervises one process rather than a wrapper that outlives its child -
# pointing launchd straight at caffeinate produced an inverted process tree and
# a python that never started.
cd /Users/brianoregan/Desktop/HRSD_Occupants/scripts || exit 1
export REPLAY_CONFIG="${REPLAY_CONFIG:-replay_config.json}"
export REPLAY_ENGINE_TAG="${REPLAY_ENGINE_TAG:-v1-engine-freeze-2.3}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /usr/bin/caffeinate -dimsu ./.venv/bin/python -u replay_supervisor.py
