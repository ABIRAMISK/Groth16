#!/bin/bash
# Circom 2 + snarkjs Groth16 timing, same method as the ZoKrates runs: one warm-up pass and five measured passes,
# circuits in a random order in every pass. Compile, setup and witness generation are done once per circuit, before
# the passes; every pass times the witness generation and `snarkjs groth16 prove -v` (with a timestamp on every log
# line) and checks the proof with `snarkjs groth16 verify`.
#   bash run_circom.sh quick    about 3 minutes: small circuits, 1 pass (do this first)
#   bash run_circom.sh          all circuits, 1 warm-up + 5 measured passes
# Settings (environment): NM = folder that contains circomlib (default ~/zk-example/node_modules),
# PTAU = powers-of-tau file (default ~/zk-example/ppot_0080_20.ptau), REPS (5), WARMUP (1).
set -u
MODE=${1:-full}
cd "$(dirname "$0")" || exit 1
NM=${NM:-$HOME/zk-example/node_modules}
PTAU=${PTAU:-$HOME/zk-example/ppot_0080_20.ptau}
REPS=${REPS:-5}; WARMUP=${WARMUP:-1}
for t in node circom snarkjs; do command -v $t >/dev/null || { echo "!!! $t not found"; exit 1; }; done
[ -f "$NM/circomlib/circuits/poseidon.circom" ] || { echo "!!! circomlib not found under $NM (set NM=...)"; exit 1; }
[ -f "$PTAU" ] || { echo "!!! powers-of-tau file not found: $PTAU (set PTAU=...)"; exit 1; }
if [ "$MODE" = quick ]; then
  LIST="poseidon_8:poseidon_chain:8:in=5 sha256:sha256_256:0:bits sq_full_2k:square_chain:2000:x=3 sq_bool_2k:square_chain:2000:x=1"
  REPS=1; WARMUP=0; SUF=_quick
else
  LIST="poseidon_64:poseidon_chain:64:in=5 poseidon_256:poseidon_chain:256:in=5 poseidon_1024:poseidon_chain:1024:in=5 sha256:sha256_256:0:bits sq_full_100k:square_chain:100000:x=3 sq_bool_100k:square_chain:100000:x=1 sq_full_300k:square_chain:300000:x=3 sq_bool_300k:square_chain:300000:x=1"
  SUF=""
fi
RES=circom_results_$(date +%Y%m%d_%H%M%S)$SUF; mkdir -p "$RES/logs" build
{
  echo "date: $(date)"; echo "uname: $(uname -a)"
  echo "node: $(node -v)"; echo "circom: $(circom --version)"; echo "snarkjs: $(snarkjs --version 2>/dev/null | head -1)"
  echo "ptau: $(basename "$PTAU") $(stat -c %s "$PTAU" 2>/dev/null) bytes"
  echo "cpu: $(powershell -NoProfile -Command '(Get-CimInstance Win32_Processor).Name' 2>/dev/null | tr -d '\r' || grep -m1 'model name' /proc/cpuinfo)"
  echo "threads: $(nproc 2>/dev/null || echo "$NUMBER_OF_PROCESSORS")"
  echo "battery status (2 = AC): $(powershell -NoProfile -Command '(Get-CimInstance Win32_Battery).BatteryStatus' 2>/dev/null | tr -d '\r')"
  echo "mode: $MODE, warm-up $WARMUP, measured $REPS"
} > "$RES/env.txt"
cat "$RES/env.txt"
bat=$(powershell -NoProfile -Command '(Get-CimInstance Win32_Battery).BatteryStatus' 2>/dev/null | tr -d '\r ')
[ "$bat" = 1 ] && { echo "!!! The laptop is on battery: plug in the charger and start again."; exit 1; }
echo "circuit,phase,seconds,constraints" > "$RES/prep.csv"
echo "circuit,pass,witness_s,prove_s,verify" > "$RES/results.csv"
now() { node -e 'console.log(Date.now()/1000)'; }
for spec in $LIST; do
  IFS=: read -r id src n inp <<< "$spec"
  key=${src}_${n}; B=build/$key; mkdir -p "$B"
  if [ ! -f "$B/circuit_final.zkey" ]; then
    if [ "$n" = 0 ]; then cp "circuits/$src.circom" "$B/circuit.circom"
    else { cat "circuits/$src.circom"; echo; echo "component main = $( [ "$src" = poseidon_chain ] && echo PoseidonChain || echo SquareChain )($n);"; } > "$B/circuit.circom"; fi
    t0=$(now); circom "$B/circuit.circom" --r1cs --wasm -l "$NM" -o "$B" > "$B/compile.log" 2>&1 || { echo "!!! compile failed: $id"; tail -5 "$B/compile.log"; exit 1; }; t1=$(now)
    info=$(node r1cs_info.js "$B/circuit.r1cs"); echo "$info" > "$B/r1cs_info.json"
    snarkjs groth16 setup "$B/circuit.r1cs" "$PTAU" "$B/circuit_final.zkey" > "$B/setup.log" 2>&1 || { echo "!!! setup failed: $id"; tail -5 "$B/setup.log"; exit 1; }; t2=$(now)
    snarkjs zkey export verificationkey "$B/circuit_final.zkey" "$B/vk.json" > /dev/null 2>&1
    c=$(echo "$info" | sed 's/.*"constraints":\([0-9]*\).*/\1/')
    echo "$key,compile,$(awk -v a="$t0" -v b="$t1" "BEGIN{printf \"%.3f\", b-a}"),$c" >> "$RES/prep.csv"; echo "$key,setup,$(awk -v a="$t1" -v b="$t2" "BEGIN{printf \"%.3f\", b-a}"),$c" >> "$RES/prep.csv"
    echo "prepared $key: $c constraints"
  fi
  cp "$B/r1cs_info.json" "$RES/logs/${key}_r1cs_info.json"
  if [ "$inp" = bits ]; then node -e 'console.log(JSON.stringify({in: Array.from({length:256}, (_, i) => (i * 7 + 3) % 5 < 2 ? 1 : 0)}))' > "$B/input_$id.json"
  else echo "{\"${inp%%=*}\": \"${inp#*=}\"}" > "$B/input_$id.json"; fi
done
total=$((WARMUP + REPS))
for pass in $(seq $((1 - WARMUP)) $REPS); do
  order=$(for s in $LIST; do echo "$s"; done | shuf)
  for spec in $order; do
    IFS=: read -r id src n inp <<< "$spec"; key=${src}_${n}; B=build/$key
    t0=$(now); node "$B/circuit_js/generate_witness.js" "$B/circuit_js/circuit.wasm" "$B/input_$id.json" "$B/w_$id.wtns" > /dev/null 2>&1 || { echo "!!! witness failed: $id"; exit 1; }; t1=$(now)
    TSLOG="$RES/logs/${id}_pass${pass}.log" node ts.js snarkjs groth16 prove "$B/circuit_final.zkey" "$B/w_$id.wtns" "$B/proof_$id.json" "$B/public_$id.json" -v
    p=$(tail -1 "$RES/logs/${id}_pass${pass}.log" | cut -f1)
    v=$(snarkjs groth16 verify "$B/vk.json" "$B/public_$id.json" "$B/proof_$id.json" 2>&1 | grep -c 'OK!')
    echo "$id,$pass,$(awk -v a="$t0" -v b="$t1" "BEGIN{printf \"%.3f\", b-a}"),$(awk -v a="$p" "BEGIN{printf \"%.4f\", a/1000}"),$v" >> "$RES/results.csv"
    echo "[pass $pass] $id: prove $(awk -v a="$p" "BEGIN{printf \"%.3f\", a/1000}") s, verified $v"
  done
done
node summary.js "$RES"
echo "Done. Send the folder $RES (right-click > Compress to ZIP)."
