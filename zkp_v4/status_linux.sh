#!/bin/bash
# Where is the run? Prints state, progress of the timing session, time elapsed and the last log lines.
cd "$(dirname "$0")" || exit 1
if pgrep -f run_all_linux.sh > /dev/null 2>&1; then echo "state: RUNNING"; else echo "state: not running (finished, or interrupted: run  bash start_linux.sh  to continue)"; fi
R=$(ls -d results_* 2> /dev/null | grep -v '_quick$' | tail -1)
if [ -n "$R" ] && [ -f "$R/raw_run.log" ]; then
  n=$(grep -c . "$R/done.list" 2> /dev/null); reps=$(grep -o 'REPS=[0-9]*' "$R/env.txt" 2> /dev/null | head -1 | cut -d= -f2); wu=$(grep -o 'WARMUP=[0-9]*' "$R/env.txt" 2> /dev/null | head -1 | cut -d= -f2)
  only=$(sed -n "s/^# run_remeasure_linux.sh.*ONLY='\([^']*\)'.*/\1/p" "$R/env.txt" 2> /dev/null | head -1); nid=$(echo $only | wc -w); [ "$nid" -gt 0 ] || nid=28
  tot=$(( (${reps:-5} + ${wu:-1}) * nid ))
  s=$(date -d "$(sed -n 's/^# run_remeasure_linux.sh.*started \([^ ]*\) .*/\1/p' "$R/env.txt" | head -1)" +%s 2> /dev/null); now=$(date +%s)
  echo "timing session $R: $n of $tot visits done$([ -n "$s" ] && awk -v s="$s" -v n="$now" -v d="$n" -v t="$tot" 'BEGIN{e=n-s; printf ", elapsed %d min, about %d min to go", e/60, (d>0? e*(t-d)/d/60 : 0)}')"
  grep '^pass ' "$R/pass_log.txt" 2> /dev/null | tail -2
fi
M=$(ls -d memory_* 2> /dev/null | grep -v '_quick$' | tail -1); [ -n "$M" ] && echo "memory profile $M: $(grep -c . "$M/done.list" 2> /dev/null) of 28 circuits done"
echo "--- last lines of the log"; tail -n 4 run_all.out 2> /dev/null | cut -c1-200
