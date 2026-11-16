#!/bin/bash
# Container side. Runs ONE ZoKrates phase and reports, for the ZoKrates process: wall time, peak resident set size (VmHWM, the
# kernel's high-water mark, read from /proc about every 20 ms) and CPU time (utime + stime from /proc/<pid>/stat).
# NOT used for timing: the polling loop would disturb it. run_remeasure.sh (zphase.sh) measures time.
# usage: bash zprofile.sh <config-folder> compile|setup|witness|proof|verify [circuit.zok]
H=${ZHOME:-/home/zokrates}
cd "$H/$1" 2>/dev/null || { echo "PROFILE phase=$2 wall=0 hwm_kib=0 cpu_ticks=0 clk_tck=100 polls=0 rc=99"; exit 0; }
ZOK=${ZOKRATES:-$(command -v zokrates || echo /home/zokrates/zokrates)}
case "$2" in
  compile) cmd=("$ZOK" compile -i "$3") ;;
  setup)   cmd=("$ZOK" setup) ;;
  witness) cmd=("$ZOK" compute-witness -a $(cat args.txt)) ;;
  proof)   cmd=("$ZOK" generate-proof) ;;
  verify)  cmd=("$ZOK" verify) ;;
  *)       echo "PROFILE phase=$2 wall=0 hwm_kib=0 cpu_ticks=0 clk_tck=100 polls=0 rc=98"; exit 0 ;;
esac
tck=$(getconf CLK_TCK 2>/dev/null || echo 100)
s=$(date +%s.%N)
"${cmd[@]}" > "phase_$2.log" 2>&1 &
pid=$!
hwm=0; ticks=0; polls=0
while kill -0 "$pid" 2>/dev/null; do
  h=""
  while read -r k v _; do if [ "$k" = "VmHWM:" ]; then h=$v; break; fi; done < "/proc/$pid/status" 2>/dev/null
  if [ -n "$h" ]; then
    hwm=$h; polls=$((polls + 1))
    if read -r -a st < "/proc/$pid/stat" 2>/dev/null; then ticks=$(( st[13] + st[14] )); fi
  fi
  sleep 0.02
done
wait "$pid"; rc=$?
e=$(date +%s.%N)
awk -v a="$s" -v b="$e" -v p="$2" -v h="$hwm" -v t="$ticks" -v k="$tck" -v n="$polls" -v rc="$rc" \
  'BEGIN{printf "PROFILE phase=%s wall=%.3f hwm_kib=%d cpu_ticks=%d clk_tck=%d polls=%d rc=%d\n", p, b-a, h, t, k, n, rc}'
head -c 3000 "phase_$2.log"
exit 0
