#!/bin/bash
# Kill/resume mid-segment, two ways, against an uninterrupted reference.
set -uo pipefail
cd ~/hrsd_occupants/hrsd/scripts
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 REPLAY_ENGINE_TAG=v1-engine-freeze-2.3
PY=./.venv/bin/python
TMP=$(mktemp -d)
cfg() { cat > "$TMP/$1.json" <<JSON
{"label":"kr_$1","master_seed":20251010,"slice_kind":"e1_estate","solve_network":false,
 "with_venues":false,"omit_datasets":["D18"],"out_root":"work/_kr_$1","rss_gate_mb":18432,"rss_warn_mb":8192,
 "segments":[{"name":"s1","year":2015,"start":"2015-01-01","end":"2015-01-03","sim_day_offset":0,"discard_output":true},
             {"name":"s2","year":2015,"start":"2015-01-04","end":"2015-01-15","sim_day_offset":3,"discard_output":true}]}
JSON
}
fp() { $PY - "$1" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1]); out = []
for seg in sorted(p for p in root.iterdir() if p.is_dir() and ".partial." not in p.name):
    ck = seg / "ckpt"; fs = sorted(ck.glob("day_*.checkpoint.json.gz"), key=lambda q: q.name)
    h = hashlib.sha256()
    for f in fs: h.update(f.name.encode()); h.update(f.read_bytes())
    out.append(f"{seg.name} {len(fs)} {h.hexdigest()}")
print("\n".join(out) or "EMPTY")
PY
}
partials() { ls -d ../work/_kr_$1/*.partial.* 2>/dev/null | while read d; do echo "  aside: $(basename $d) with $(ls $d/ckpt 2>/dev/null | grep -c day_) checkpoint(s)"; done; }
wait_ckpts() { for _ in $(seq 1 600); do n=$(ls ../work/_kr_$1/s2/ckpt 2>/dev/null | grep -c day_); [ "${n:-0}" -ge 4 ] && { echo "  s2 has $n checkpoints"; return; }; sleep 1; done; echo "  timeout waiting"; }

echo "=== R: reference, uninterrupted ==="; cfg R
REPLAY_CONFIG="$TMP/R.json" $PY -u replay_supervisor.py > "$TMP/R.log" 2>&1; echo "  exit $?"
FR=$(fp ../work/_kr_R); echo "$FR" | sed 's/^/  /'

echo "=== K1: kill only the s2 child mid-segment (supervisor retries) ==="; cfg K1
REPLAY_CONFIG="$TMP/K1.json" $PY -u replay_supervisor.py > "$TMP/K1.log" 2>&1 & SUP=$!
wait_ckpts K1; pkill -KILL -f "[r]eplay_supervisor.py --only s2" && echo "  SIGKILLed the s2 child"
wait $SUP; echo "  supervisor exit $?"
F1=$(fp ../work/_kr_K1); echo "$F1" | sed 's/^/  /'; partials K1

echo "=== K2: SIGKILL supervisor + child mid-segment, then restart (crash / systemd restart) ==="; cfg K2
setsid bash -c "REPLAY_CONFIG='$TMP/K2.json' exec $PY -u replay_supervisor.py" > "$TMP/K2a.log" 2>&1 & SID=$!
wait_ckpts K2; kill -KILL -- -$SID 2>/dev/null && echo "  SIGKILLed the whole process group"; sleep 2
pgrep -af "[_]kr_K2|K2.json" || echo "  nothing left running"
REPLAY_CONFIG="$TMP/K2.json" $PY -u replay_supervisor.py > "$TMP/K2b.log" 2>&1; echo "  restart exit $?"
F2=$(fp ../work/_kr_K2); echo "$F2" | sed 's/^/  /'; partials K2

echo; rc=0
[ "$FR" = "$F1" ] && echo "PASS  child kill + retry identical to reference" || { echo "FAIL  K1 != R"; rc=1; }
[ "$FR" = "$F2" ] && echo "PASS  full crash + restart identical to reference" || { echo "FAIL  K2 != R"; rc=1; }
echo "$FR" | grep -q '^s2 12 ' || { echo "FAIL  reference s2 does not have 12 checkpoints"; rc=1; }
rm -rf ../work/_kr_R ../work/_kr_K1 ../work/_kr_K2 "$TMP"
exit $rc
