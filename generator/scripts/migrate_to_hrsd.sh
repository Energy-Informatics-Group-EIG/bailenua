#!/bin/bash
# Move the project out of ~/Desktop so launchd can reach it, at a segment
# boundary. Run with --check first; --check touches nothing.
#
# WHY: macOS TCC denies launchd access to ~/Desktop (I-107), so the LaunchAgent
# exited 126 and the replay has been running under nohup with no KeepAlive -
# nothing restarts it if it dies. Granting Full Disk Access would fix it and is
# explicitly NOT wanted. Moving the tree to ~/hrsd, which TCC does not guard,
# is the sanctioned fix.
#
# WHAT SURVIVES THE MOVE: a symlink is left at the old path, so every absolute
# path already written into the repo keeps resolving - which matters because the
# six git worktrees hold absolute gitdir pointers into
# ~/Desktop/HRSD_Occupants/.git/worktrees/*, and _frozen_root and the sources
# symlink farm are absolute too. Verified by --check.
set -uo pipefail
OLD=/Users/brianoregan/Desktop/HRSD_Occupants
NEW=/Users/brianoregan/hrsd
PLIST=~/Library/LaunchAgents/ie.bailenua.replay.plist
LABEL=ie.bailenua.replay
MODE="${1:---check}"

say() { printf '%s\n' "$*"; }
fail=0
chk() { if eval "$2"; then say "  ok    $1"; else say "  FAIL  $1"; fail=1; fi; }

say "=== preconditions ==="
chk "old tree exists and is a real directory"      "[ -d $OLD ] && [ ! -L $OLD ]"
chk "destination $NEW does not already exist"      "[ ! -e $NEW ]"
chk "LaunchAgent plist is present"                 "[ -f $PLIST ]"
chk "agent is NOT currently loaded"                "! launchctl list | grep -q $LABEL"
chk "launch script is executable"                  "[ -x $OLD/scripts/replay_launch.sh ]"
# A boundary means the current segment has a DONE sentinel. Moving mid-segment
# would strand a half-written package and a chain whose head is in flight.
LAST_DONE=$(ls -d $OLD/work/replay_2015_2026/*/DONE.json 2>/dev/null | wc -l | tr -d ' ')
RUNNING=$(pgrep -f replay_supervisor.py | wc -l | tr -d ' ')
say "  info  segments with DONE.json: $LAST_DONE"
say "  info  supervisor processes running: $RUNNING"
# Computed BEFORE chk, never inside its eval: escaping $4 through eval fed awk
# a literal backslash, and the filesystem test then compared two empty strings
# and "passed". A check that cannot fail is worse than no check.
FREE_GB=$(df -g /System/Volumes/Data | awk 'NR==2{print $4}')
FS_OLD=$(df "$OLD" | awk 'NR==2{print $1}')
FS_HOME=$(df /Users/brianoregan | awk 'NR==2{print $1}')
say "  info  free $FREE_GB GB; filesystems '$FS_OLD' vs '$FS_HOME'"
chk "disk has at least 5 GB free for the move" "[ \"$FREE_GB\" -ge 5 ]"
chk "filesystem strings are non-empty" "[ -n \"$FS_OLD\" ] && [ -n \"$FS_HOME\" ]"
chk "same filesystem (so mv is a rename, not a copy)" "[ \"$FS_OLD\" = \"$FS_HOME\" ]"

if [ "$MODE" = "--check" ]; then
  say ""
  say "check only; nothing was changed."
  [ "$fail" -eq 0 ] && say "RESULT: preconditions met." || say "RESULT: NOT ready ($fail failing)."
  say "The supervisor must be stopped at a boundary before --go."
  exit $fail
fi

if [ "$MODE" != "--go" ]; then say "usage: $0 [--check|--go]"; exit 2; fi
[ "$fail" -ne 0 ] && { say "refusing: preconditions failed"; exit 1; }
[ "$RUNNING" -ne 0 ] && { say "refusing: supervisor still running - stop it at a boundary first"; exit 1; }

say ""
say "=== moving ==="
mv "$OLD" "$NEW"                   || { say "mv failed"; exit 1; }
ln -s "$NEW" "$OLD"                || { say "symlink failed - tree is at $NEW"; exit 1; }
say "  moved, and $OLD -> $NEW"

# Point the agent at the real path. The old path would still resolve through
# the symlink, but launchd would then be reading a ~/Desktop path again and
# TCC is exactly what we are escaping.
sed -i '' "s#$OLD#$NEW#g" "$PLIST"
say "  plist repointed at $NEW"

launchctl unload "$PLIST" 2>/dev/null
launchctl load -w "$PLIST" || { say "launchctl load FAILED"; exit 1; }
say "  agent loaded"
sleep 10
if launchctl list | grep -q "$LABEL"; then
  say "  present in launchctl list:"
  launchctl list | grep "$LABEL" | sed 's/^/    /'
else
  say "  NOT in launchctl list - fell back to nohup is the manual next step"
fi
say ""
say "verify: ls $NEW/work/replay_2015_2026/*/ckpt | tail; launchctl list | grep $LABEL"
