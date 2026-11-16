#!/bin/bash
# Everything for the paper on THIS machine, one command: check, (1) native baseline, (2) the 28-circuit ZKP session, (3) the memory profile, then packs the results.
# Leave the computer alone, plugged in, Power mode = Best performance. About 2.5 hours. Start it with one command and do not type anything else into the window.
# If a step stops, run only that step again (commands are printed), then  bash pack_results.sh  at the end.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")" || exit 1
bash check_setup.sh < /dev/null || exit 1
PY=$(cat .pybin 2>/dev/null)
echo; echo "=============== step 1/3: native baseline (about 2 minutes) ==============="
if [ -n "$PY" ]; then $PY classical_bench.py $CLASSICAL_ARGS < /dev/null || echo "!!! step 1 failed. Run it again with:  $PY classical_bench.py"
else echo "step 1 skipped: no Python with the cryptography package on this machine (see the check above)"; fi
echo; echo "=============== step 2/3: ZKP session, 28 circuits (about 2 hours) ==============="
bash run_remeasure.sh < /dev/null || { echo "!!! step 2 stopped. Continue with:  RESUME=<results folder printed above> bash run_remeasure.sh"; exit 1; }
echo; echo "=============== step 3/3: memory profile (about 20 minutes) ==============="
bash run_memory_profile.sh < /dev/null || echo "!!! step 3 failed. Run it again with:  bash run_memory_profile.sh"
echo; echo "=============== packing ==============="
bash pack_results.sh < /dev/null
echo; echo "All steps finished $(date -u +%FT%TZ). Attach the zip named above."
