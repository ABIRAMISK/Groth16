#!/bin/bash
# Everything for the paper on THIS Linux machine: (1) native baseline, (2) the 28-circuit ZKP session, (3) memory profile, then packs the results.
# Resumes by itself: run it again after an interruption and it continues the unfinished folder.   bash run_all_linux.sh quick   = a 10-minute functional check.
cd "$(dirname "$0")" || exit 1
[ -f .zkmode ] || bash check_setup_linux.sh < /dev/null || exit 1
export ZK_MODE=$(cat .zkmode)
Q=""; [ "${1:-}" = quick ] && { Q=quick; export ONLY=${ONLY:-"merkle_8 rsa_256_1 merkle_64c sha256_ecc"} MEM_SUFFIX=_quick; }
finished()   { local d; for d in $(ls -d "$1"_* 2> /dev/null | grep -v '_quick$'); do grep -q '^================ finished' "$d/raw_run.log" 2> /dev/null && return 0; done; return 1; }
unfinished() { local d; for d in $(ls -d "$1"_* 2> /dev/null | grep -v '_quick$'); do grep -q '^================ finished' "$d/raw_run.log" 2> /dev/null || { echo "$d"; return 0; }; done; return 1; }
echo "started $(date -u +%FT%TZ)   mode=$ZK_MODE   cpus=$(nproc)   $(cpu_name 2> /dev/null)"
echo; echo "=============== step 1/3: native baseline (about 2 minutes) ==============="
has_native() { local d; for d in $(ls -d native_* 2> /dev/null | grep -v '_quick$'); do [ -f "$d/raw_classical.csv" ] && return 0; done; return 1; }
if has_native && [ -z "$Q" ]; then echo "already done"
else python3 classical_bench.py ${Q:+--quick} $CLASSICAL_ARGS < /dev/null || echo "!!! step 1 failed (the rest does not depend on it)"; fi
echo; echo "=============== step 2/3: ZKP session, 28 circuits ==============="
if [ -z "$Q" ] && finished results; then echo "already finished"
else
  R=$([ -z "$Q" ] && unfinished results)
  if [ -n "$R" ]; then echo "resuming $R"; RESUME=$R bash run_remeasure_linux.sh $Q < /dev/null || { echo "!!! step 2 stopped; run this command again to continue"; exit 1; }
  else bash run_remeasure_linux.sh $Q < /dev/null || { echo "!!! step 2 stopped; run this command again to continue"; exit 1; }; fi
fi
echo; echo "=============== step 3/3: memory profile ==============="
if [ -z "$Q" ] && finished memory; then echo "already finished"
else
  R=$([ -z "$Q" ] && unfinished memory)
  if [ -n "$R" ]; then echo "resuming $R"; RESUME=$R bash run_memory_profile_linux.sh < /dev/null || echo "!!! step 3 failed; run this command again"
  else bash run_memory_profile_linux.sh < /dev/null || echo "!!! step 3 failed; run this command again"; fi
fi
echo; echo "=============== packing ==============="
if [ -z "$Q" ]; then bash pack_results_linux.sh < /dev/null; else echo "(quick check: nothing is packed; the check passed if no line above starts with !!!)"; fi
echo; echo "All steps finished $(date -u +%FT%TZ)."
