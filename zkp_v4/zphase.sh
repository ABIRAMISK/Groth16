#!/bin/bash
# Container side. Runs ONE ZoKrates phase in a prepared configuration folder and reports its own wall time, so the host
# can separate the cost of the phase from the cost of `docker exec`.
# usage: bash zphase.sh <config-folder> compile|setup|witness|proof|verify [circuit.zok]
# <config-folder> is relative to $ZHOME (default /home/zokrates). Default ZoKrates file names are used (out, abi.json,
# proving.key, verification.key, witness, proof.json), exactly as in the original verify_*.sh scripts.
H=${ZHOME:-/home/zokrates}
cd "$H/$1" 2>/dev/null || { echo "INNER 0.000 RC 99"; echo "ERROR: no such folder $H/$1"; exit 0; }
ZOK=${ZOKRATES:-$(command -v zokrates || echo /home/zokrates/zokrates)}
case "$2" in
  compile) cmd=("$ZOK" compile -i "$3") ;;
  setup)   cmd=("$ZOK" setup) ;;
  witness) cmd=("$ZOK" compute-witness -a $(cat args.txt)) ;;
  proof)   cmd=("$ZOK" generate-proof) ;;
  verify)  cmd=("$ZOK" verify) ;;
  *)       echo "INNER 0.000 RC 98"; echo "ERROR: unknown phase $2"; exit 0 ;;
esac
s=$(date +%s.%N)
"${cmd[@]}" > "phase_$2.log" 2>&1
rc=$?
e=$(date +%s.%N)
awk -v a="$s" -v b="$e" -v rc="$rc" 'BEGIN{printf "INNER %.3f RC %d\n", b-a, rc}'
head -c 3000 "phase_$2.log"
exit 0
