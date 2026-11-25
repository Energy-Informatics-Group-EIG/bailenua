# Shared, non-secret environment for the Baile Nua v1 run on this instance.
# Sourced by every ops script. The B2 key lives in ~/.b2_hrsd_occupants.env and
# is sourced only by post_year.sh, only for the rclone calls.
export HRSD=/home/ubuntu/hrsd_occupants/hrsd
export STATUS="${STATUS:-$HRSD/status}"
export OPS=/home/ubuntu/hrsd_occupants/ops
export RUN="${RUN:-$HRSD/work/replay_2015_2026}"
export PY="$HRSD/scripts/.venv/bin/python"
export REPLAY_CONFIG=replay_config.json
export REPLAY_ENGINE_TAG=v1-engine-freeze-2.3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export B2_ENV_FILE=/home/ubuntu/.b2_hrsd_occupants.env
export B2_DEST="${B2_DEST:-b2eig:hrsd-occupants/v1}"
export SEGMENTS="${SEGMENTS:-warmup_2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026}"
