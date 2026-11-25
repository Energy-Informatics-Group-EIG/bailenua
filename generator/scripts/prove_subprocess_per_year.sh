#!/bin/bash
# D-148 kill/resume proof: running each year as a fresh subprocess must give
# byte-identical results, including across a kill.
#
# Three runs on a tiny two-segment config at estate scale:
#   A  uninterrupted, subprocess-per-year            -> the reference
#   B  killed during segment 2, then resumed         -> must equal A
#   C  uninterrupted, old single-process (--in-process) -> must also equal A
#
# C is the one that matters for "digest-neutral": it shows the new process
# arrangement computes what the old one did, not merely that it is
# self-consistent.
set -uo pipefail
cd "$(dirname "$0")"
VENV=./.venv/bin/python
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mk_cfg() {  # $1 = out_root
  cat > "$TMP/cfg_$2.json" <<JSON
{
  "label": "proof_$2",
  "master_seed": 20251010,
  "slice_kind": "e1_estate",
  "solve_network": false,
  "with_venues": false,
  "omit_datasets": ["D18"],
  "out_root": "$1",
  "rss_gate_mb": 18432,
  "rss_warn_mb": 8192,
  "segments": [
    {"name": "s1", "year": 2015, "start": "2015-01-01", "end": "2015-01-03",
     "sim_day_offset": 0, "discard_output": true},
    {"name": "s2", "year": 2015, "start": "2015-01-04", "end": "2015-01-06",
     "sim_day_offset": 3, "discard_output": true}
  ]
}
JSON
}

fingerprint() {  # chain heads + checkpoint digests, which is the simulated state
  $VENV - "$1" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
out = []
for seg in sorted(p for p in root.iterdir() if p.is_dir()):
    ck = seg / "ckpt"
    if not ck.is_dir():
        continue
    h = hashlib.sha256()
    for f in sorted(ck.glob("day_*.checkpoint.json.gz"), key=lambda q: q.name):
        h.update(f.name.encode()); h.update(f.read_bytes())
    out.append(f"{seg.name} {len(list(ck.glob('day_*.checkpoint.json.gz')))} {h.hexdigest()}")
print("\n".join(out) or "EMPTY")
PY
}

echo "=== A: uninterrupted, subprocess per year ==="
mk_cfg "work/_proof_A" A
REPLAY_CONFIG="$TMP/cfg_A.json" $VENV -u replay_supervisor.py > "$TMP/A.log" 2>&1
echo "  exit $?"; FA=$(fingerprint ../work/_proof_A); echo "$FA" | sed 's/^/  /'
grep -c spawning ../work/_proof_A/children.log 2>/dev/null | sed 's/^/  children spawned: /'

echo "=== B: killed during segment 2, then resumed ==="
mk_cfg "work/_proof_B" B
REPLAY_CONFIG="$TMP/cfg_B.json" $VENV -u replay_supervisor.py > "$TMP/B1.log" 2>&1 &
SUP=$!
# wait for s1 to finish and s2's child to start, then kill the CHILD
for _ in $(seq 1 240); do
  [ -f ../work/_proof_B/s1/DONE.json ] && break
  sleep 1
done
sleep 3
pkill -f "replay_supervisor.py --only s2" 2>/dev/null && echo "  killed the s2 child"
wait $SUP 2>/dev/null; echo "  first supervisor exited $?"
REPLAY_CONFIG="$TMP/cfg_B.json" $VENV -u replay_supervisor.py > "$TMP/B2.log" 2>&1
echo "  resume exit $?"; FB=$(fingerprint ../work/_proof_B); echo "$FB" | sed 's/^/  /'

echo "=== C: uninterrupted, OLD single-process arrangement ==="
mk_cfg "work/_proof_C" C
REPLAY_CONFIG="$TMP/cfg_C.json" $VENV -u replay_supervisor.py --in-process > "$TMP/C.log" 2>&1
echo "  exit $?"; FC=$(fingerprint ../work/_proof_C); echo "$FC" | sed 's/^/  /'

echo
rc=0
[ "$FA" = "$FB" ] && echo "PASS  kill/resume is byte-identical (A == B)" || { echo "FAIL  A != B"; rc=1; }
[ "$FA" = "$FC" ] && echo "PASS  subprocess == single-process (A == C)" || { echo "FAIL  A != C"; rc=1; }
[ "$FA" = "EMPTY" ] && { echo "FAIL  fingerprint is empty - nothing was proved"; rc=1; }
rm -rf ../work/_proof_A ../work/_proof_B ../work/_proof_C
exit $rc
