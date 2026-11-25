#!/bin/bash
# One replay watch tick. Touches ONE directory (the live segment's ckpt) plus two
# small status files - never a full-tree walk (D-151).
R=/Users/brianoregan/hrsd
SEG=$(awk '{print $3}' "$R/status/LAST.txt" 2>/dev/null)
[ -d "$R/work/replay_2015_2026/$SEG/ckpt" ] || \
  SEG=$(ls "$R/work/replay_2015_2026" | grep -E '^(19|20)[0-9][0-9]$' | tail -1)
CK="$R/work/replay_2015_2026/$SEG/ckpt"

SWAP=$(sysctl -n vm.swapusage | awk '{gsub("M","");t=$3;u=$6; if(t+0>0) printf "%.1f",(u/t)*100; else printf "0.0"}')
MEM=$(vm_stat | awk '/Pages free/{f=$3}/Pages speculative/{s=$3}/Pages active/{a=$3}/Pages inactive/{i=$3}/Pages wired/{w=$4}
  END{gsub(/\./,"",f);gsub(/\./,"",s);gsub(/\./,"",a);gsub(/\./,"",i);gsub(/\./,"",w);
      printf "%.1f",((f+s)/(f+s+a+i+w))*100}')
DISK=$(df -g /System/Volumes/Data | awk 'NR==2{print $4}')
RSS=$(ps -axo rss,command | awk '/replay_supervisor\.py --only/ && !/awk/{s+=$1} END{printf "%.0f", s/1024}')
PID=$(pgrep -f "replay_supervisor.py --only" | head -1)

# one directory stat; day number and per-day gaps
TMP=$(mktemp)
stat -f "%m %N" "$CK"/day_*.checkpoint.json.gz 2>/dev/null | sort -n > "$TMP"
DAY=$(awk 'END{n=$2; sub(/.*day_/,"",n); sub(/\..*/,"",n); print n+0}' "$TMP")
NDAY=$(wc -l < "$TMP" | tr -d ' ')
MED=$(awk 'NR>1{print $1-p} {p=$1}' "$TMP" | sort -n | awk '{g[NR]=$1} END{if(NR<1){print 0;exit} print (NR%2)?g[int(NR/2)+1]:(g[NR/2]+g[NR/2+1])/2}')
read RATE STALLS <<<"$(awk -v m="$MED" 'NR>1{g=$1-p; if(m>0 && g>2*m) st++; else {s+=g;c++}} {p=$1} END{printf "%.0f %d", (c?s/c:m), st+0}' "$TMP")"
rm -f "$TMP"

printf "%s  sim_day %s (%s d%s/366)  swap %s%%  mem free %s%%  disk %s GiB  %s s/day (%s stall%s excl)  RSS %s MB  pid %s\n" \
  "$(date '+%H:%M')" "$DAY" "$SEG" "$NDAY" "$SWAP" "$MEM" "$DISK" "$RATE" "$STALLS" "$([ "$STALLS" = 1 ] || echo s)" "$RSS" "${PID:-NONE}"
