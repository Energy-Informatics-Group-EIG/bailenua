#!/usr/bin/env bash
# Backup snapshot of the HRSD_Occupants working tree.
#
# Written because the 2026-10-12 snapshot was assembled by hand and its
# MANIFEST had to be reverse-engineered to verify it. Same layout as that one:
# one zstd tarball per subtree, a two-section manifest (every file inside each
# archive, then the archives themselves), and a SNAPSHOT.md recording git state.
#
# Usage: make_snapshot.sh <label>
set -euo pipefail
cd "$(dirname "$0")/.."
LABEL="${1:?usage: make_snapshot.sh <label>}"
DEST="snapshots/$LABEL"
[ -e "$DEST" ] && { echo "REFUSING: $DEST already exists (snapshots are immutable)"; exit 1; }
mkdir -p "$DEST"

SUBTREES=(v1 scripts docs sources)
MAN="$DEST/MANIFEST.sha256"
{
  echo "# MANIFEST.sha256 - HRSD_Occupants $LABEL (backup snapshot)"
  echo "# Section 1: SHA-256 of every file INSIDE each archive. Paths are as stored"
  echo "#            in the archive (relative to the project root)."
  echo "# Section 2: SHA-256 of each archive file itself."
} > "$MAN"

for t in "${SUBTREES[@]}"; do
  [ -d "$t" ] || { echo "skip $t (absent)"; continue; }
  echo "archiving $t ..."
  tar --zstd -cf "$DEST/$t.tar.zst" "$t"
  n=$(tar --zstd -tf "$DEST/$t.tar.zst" | grep -vc '/$' || true)
  echo "" >> "$MAN"
  echo "# --- files inside $t.tar.zst ($n files) ---" >> "$MAN"
  find "$t" -type f -print0 | sort -z | xargs -0 shasum -a 256 >> "$MAN"
done

echo "" >> "$MAN"
echo "# --- the archives themselves ---" >> "$MAN"
( cd "$DEST" && shasum -a 256 *.tar.zst >> "MANIFEST.sha256" )

HEAD_SHA=$(git rev-parse HEAD); HEAD_SHORT=$(git rev-parse --short HEAD)
HEAD_SUBJ=$(git log -1 --format=%s); HEAD_DATE=$(git log -1 --format=%cd)
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
TAGS=$(git tag --points-at HEAD | tr '\n' ' '); [ -z "$TAGS" ] && TAGS="(none at HEAD)"
{
  echo "# $LABEL — backup snapshot"
  echo
  echo "**Backup snapshot. Not a release. Do not use for results.**"
  echo
  echo "## When"; echo
  echo "| | |"; echo "|---|---|"
  echo "| Created | $(date '+%Y-%m-%d %H:%M %Z') |"
  echo "| Host | $(whoami) ($(uname -s | tr 'A-Z' 'a-z') $(uname -r)) |"
  echo "| Source tree | \`$(pwd)\` |"
  echo
  echo "## Git"; echo
  echo "| | |"; echo "|---|---|"
  echo "| HEAD | \`$HEAD_SHA\` |"
  echo "| Short | \`$HEAD_SHORT\` |"
  echo "| Subject | $HEAD_SUBJ |"
  echo "| Committed | $HEAD_DATE |"
  echo "| Branch | \`$(git rev-parse --abbrev-ref HEAD)\` |"
  echo "| Tags at HEAD | $TAGS |"
  echo "| Working tree | $( [ "$DIRTY" -eq 0 ] && echo clean || echo "dirty — $DIRTY entries in \`git status --porcelain\`" ) |"
  echo
  echo "The archives capture the **working tree as it stood**, not the committed"
  echo "state. Where the two differ, the archive is authoritative for what was on disk."
  echo
  echo "## Archives"; echo
  echo "| Archive | Size | Files |"; echo "|---|---|---|"
  for t in "${SUBTREES[@]}"; do
    [ -f "$DEST/$t.tar.zst" ] || continue
    printf "| \`%s.tar.zst\` | %s | %s |\n" "$t" \
      "$(du -h "$DEST/$t.tar.zst" | cut -f1 | tr -d ' ')" \
      "$(tar --zstd -tf "$DEST/$t.tar.zst" | grep -vc '/$' || true)"
  done
  echo
  echo "## Verify"; echo
  echo '```'
  echo "cd \"\$(git rev-parse --show-toplevel)\""
  echo "shasum -a 256 -c <(sed -n '/--- the archives/,\$p' $DEST/MANIFEST.sha256 | grep 'tar.zst\$')"
  echo "shasum -a 256 -c <(grep -v '^#' $DEST/MANIFEST.sha256 | grep -v 'tar.zst\$')"
  echo '```'
} > "$DEST/SNAPSHOT.md"

echo; echo "snapshot written to $DEST"; du -sh "$DEST"
