#!/bin/bash
# Runs several phase-decomposition runs one after the other on one Linux machine (Colab), so that all of them use the same VM.
# usage: bash run_queue_linux.sh "bellman:full ark:eddsa bellman:eddsa"
# A run that already has a finished folder is skipped; an unfinished folder of the same kind is continued.
cd "$(dirname "$0")" || exit 1
for spec in ${1:-"bellman:full ark:eddsa bellman:eddsa"}; do
  bk=${spec%%:*}; mode=${spec##*:}; [ "$bk" = ark ] && bk=""
  pre="phases_${bk:+${bk}_}2"; case "$mode" in full) suf="";; quick) suf="_quick";; *quick) suf="_${mode%quick}_quick";; *) suf="_$mode";; esac
  done_dir=""; open_dir=""
  for d in $(ls -d ${pre}* 2>/dev/null); do
    [ -d "$d" ] || continue
    if [ -n "$suf" ]; then [[ "$d" == *"$suf" ]] || continue; else [[ "$d" =~ _[0-9]{8}_[0-9]{6}$ ]] || continue; fi
    if grep -q '================ finished' "$d/raw_run.log" 2>/dev/null; then done_dir=$d; else open_dir=$d; fi
  done
  if [ -n "$done_dir" ]; then echo "=== ${bk:-ark} $mode: already finished in $done_dir, skipped"; continue; fi
  echo "=== ${bk:-ark} $mode: $([ -n "$open_dir" ] && echo "continuing $open_dir" || echo "new run")  $(date -u +%FT%TZ)"
  m=$mode; [ "$m" = full ] && m=""
  if [ -n "$open_dir" ]; then RESUME=$open_dir BACKEND=$bk bash run_phases_linux.sh $m; else BACKEND=$bk bash run_phases_linux.sh $m; fi
done
echo "=== QUEUE FINISHED $(date -u +%FT%TZ)"
