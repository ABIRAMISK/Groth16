#!/bin/bash
# Phase decomposition of `zokrates generate-proof` (ZoKrates 0.8.7) with an instrumented binary.
# Derived from run_phases_linux.sh: same circuits, same storage, same warm-up + measured passes in random order.
# Differences: the instrumented binary zokrates_timers (ZoKrates 0.8.7 source + timers, statically linked) is used for every
# phase; the 21 full-pipeline circuits are run; there is no bind-mount control.
# Each proof prints lines "ZKT <phase> <seconds>" which end up in raw_run.log; phases_extract.py turns them into phases.csv.
#
#   bash run_phases_linux.sh eddsa                     the two EdDSA verifiers only (frozen-model test): 1 warm-up + 5 measured passes
#   bash run_phases_linux.sh quick                     about 3 minutes: 4 small circuits, 1 replicate (do this first)
#   bash run_phases_linux.sh                           all 21 circuits, ark back end (the default of ZoKrates): 1 warm-up + 5 measured passes
#   FAST=1 bash run_phases_linux.sh [mode]            the same with the cached-matrix prover (matrices written once at setup; ark only)
#   BACKEND=bellman bash run_phases_linux.sh [quick]   the same with the bellman back end (setup, proof and verification use it)
#   RESUME=phases_... bash run_phases_linux.sh [mode]  continue an interrupted run (give BACKEND again if it was set)
export MSYS_NO_PATHCONV=1          # stops Git Bash from rewriting container paths such as /bind into C:/Program Files/Git/...
cd "$(dirname "$0")" || exit 1
ZK_MODE=${ZK_MODE:-$(cat .zkmode 2>/dev/null)}; ZK_MODE=${ZK_MODE:-docker}; export ZK_MODE
NH=${NATIVE_HOME:-/tmp/zk_native}; BACKEND=${BACKEND:-}; TIMERS=zokrates_timers; FAST=${FAST:-}; [ -n "$FAST" ] && TIMERS=zokrates_fast
[ -n "$FAST" ] && [ -n "$BACKEND" ] && { echo "FAST=1 works with the ark back end only: leave BACKEND unset."; exit 1; }
[ -f "$TIMERS" ] && [ -f zok_wrap.sh ] || { echo "Missing zokrates_timers or zok_wrap.sh: copy every file of the kit into this folder."; exit 1; }
chmod +x "$TIMERS" zok_wrap.sh
if [ -n "$BACKEND" ] || [ -n "$FAST" ]; then ZOK_BIN=$PWD/zok_wrap.sh; else ZOK_BIN=$PWD/$TIMERS; fi; ZOK_STD=${ZOK_STD:-$PWD/zokrates_bin/stdlib}; NOWAIT=${NOWAIT:-1}
source ./envlib_linux.sh

MODE=${1:-full}
IMAGE=${IMAGE:-zokrates/zokrates:0.8.7}
REPS=${REPS:-5}; WARMUP=${WARMUP:-1}; CONTROL=0
CONTROL_IDS=${CONTROL_IDS:-"poseidon_256 rsa_1024_64"}
ONLY=${ONLY:-}
SUFFIX=""; MODEARG=""; [ "$MODE" != full ] && MODEARG=" $MODE"
if [ "$MODE" = quick ]; then
  REPS=1; WARMUP=0; CONTROL=0; SUFFIX="_quick"
  [ -z "$ONLY" ] && ONLY="merkle_8 rsa_256_1 rsa1024real sha256_ecc"
elif [ "$MODE" = rsareal ] || [ "$MODE" = rsarealquick ]; then
  ONLY="rsa1024real rsa2048real rsa3072real rsa4096real"; CONTROL=0; SUFFIX="_rsareal"
  [ "$MODE" = rsarealquick ] && { REPS=1; WARMUP=0; SUFFIX="_rsareal_quick"; }
elif [ "$MODE" = synth ] || [ "$MODE" = synthquick ]; then
  ONLY="synth_full_100k synth_bool_100k synth_full_300k synth_bool_300k"; CONTROL=0; SUFFIX="_synth"
  [ "$MODE" = synthquick ] && { REPS=1; WARMUP=0; SUFFIX="_synth_quick"; }
elif [ "$MODE" = eddsa ] || [ "$MODE" = eddsaquick ]; then
  ONLY="eddsa_sha256 eddsa_poseidon"; CONTROL=0; SUFFIX="_eddsa"
  [ "$MODE" = eddsaquick ] && { REPS=1; WARMUP=0; SUFFIX="_eddsa_quick"; }
elif [ "$MODE" = ecdsa ] || [ "$MODE" = ecdsaquick ]; then
  ONLY="ecdsa_secp256k1"; CONTROL=0; SUFFIX="_ecdsa"
  [ "$MODE" = ecdsaquick ] && { REPS=1; WARMUP=0; SUFFIX="_ecdsa_quick"; }
fi
[ "$MODE" = full ] && [ -z "$ONLY" ] && ONLY="merkle_8 merkle_16 merkle_32 poseidon_64 poseidon_256 poseidon_512 poseidon_1024 rsa_256_1 rsa_256_64 rsa_1024_64 rsa1024real rsa2048real rsa3072real rsa4096real ecdsa_secp256k1 sha256_ecc sha256_rsa synth_full_100k synth_bool_100k synth_full_300k synth_bool_300k"
if [ -n "$BACKEND" ] || [ -n "$FAST" ]; then ZOKP=/home/zokrates/zok_wrap.sh; else ZOKP=/home/zokrates/zokrates_timers; fi
RES=${RESUME:-phases${FAST:+_fast}${BACKEND:+_$BACKEND}_$(date +%Y%m%d_%H%M%S)$SUFFIX}
mkdir -p "$RES" || exit 1
exec > >(tee -a "$RES/raw_run.log") 2>&1

# id|family|parameter|type|expected constraints|p1|p2      (type suffix _c = compile-only, as in verify_compile_only.sh)
CONFIGS=(
  "merkle_8|Merkle path|d=8|merkle|1962|8|"
  "merkle_16|Merkle path|d=16|merkle|3922|16|"
  "merkle_32|Merkle path|d=32|merkle|7842|32|"
  "poseidon_64|Poseidon chain|n=64|poseidon|13634|64|"
  "poseidon_256|Poseidon chain|n=256|poseidon|54530|256|"
  "poseidon_512|Poseidon chain|n=512|poseidon|109058|512|"
  "poseidon_1024|Poseidon chain|n=1024|poseidon|218114|1024|"
  "rsa_256_1|RSA accumulator|b=256,r=1|rsa|2559|256|1"
  "rsa_256_64|RSA accumulator|b=256,r=64|rsa|66945|256|64"
  "rsa_1024_64|RSA accumulator|b=1024,r=64|rsa|268161|1024|64"
  "rsa1024real|RSA-1024 verify (real)|e=65537 W=121 K=9|rsareal|76604|1024|"
  "rsa2048real|RSA-2048 verify (real)|e=65537 W=121 K=17|rsa2048|153484||"
  "rsa3072real|RSA-3072 verify (real)|e=65537 W=121 K=26|rsareal|244870|3072|"
  "rsa4096real|RSA-4096 verify (real)|e=65537 W=121 K=34|rsareal|331848|4096|"
  "ecdsa_secp256k1|ECDSA secp256k1 verify (real)|5 limbs of 60 bits, 2-bit Strauss-Shamir|ecdsa|842212||"
  "sha256_ecc|SHA-256 compression|commitment circuit, ECC-derived input|sha|27214|ecc|"
  "sha256_rsa|SHA-256 compression|commitment circuit, RSA-derived input|sha|27214|rsa|"
  "synth_full_100k|Synthetic full-width chain|N=100000, x=x*x+1 chain|synth|100001|full|100k"
  "synth_bool_100k|Synthetic boolean chain|N=50000, XOR/OR chain of bits|synth|100002|bool|100k"
  "synth_full_300k|Synthetic full-width chain|N=300000, x=x*x+1 chain|synth|300001|full|300k"
  "synth_bool_300k|Synthetic boolean chain|N=150000, XOR/OR chain of bits|synth|300002|bool|300k"
  "eddsa_sha256|BabyJubJub EdDSA verify|SHA-256 challenge (standard library)|eddsa|94181|sha256|"
  "eddsa_poseidon|BabyJubJub EdDSA verify|Poseidon challenge (variant)|eddsa|15211|poseidon|"
  "merkle_64c|Merkle path|d=64|merkle_c|15682|64|"
  "rsa_256_8c|RSA accumulator|b=256,r=8|rsa_c|9713|256|8"
  "rsa_512_1c|RSA accumulator|b=512,r=1|rsa_c|5119|512|1"
  "rsa_512_8c|RSA accumulator|b=512,r=8|rsa_c|19441|512|8"
  "rsa_512_64c|RSA accumulator|b=512,r=64|rsa_c|134017|512|64"
  "rsa_1024_1c|RSA accumulator|b=1024,r=1|rsa_c|10239|1024|1"
  "rsa_1024_8c|RSA accumulator|b=1024,r=8|rsa_c|38897|1024|8"
)
declare -A FAM PAR TYP EXP P1 P2 CIRC
ALL_IDS=()
for line in "${CONFIGS[@]}"; do
  IFS='|' read -r id fam par typ exp p1 p2 <<< "$line"
  FAM[$id]=$fam; PAR[$id]=$par; TYP[$id]=$typ; EXP[$id]=$exp; P1[$id]=$p1; P2[$id]=$p2; ALL_IDS+=("$id")
done

# Values that the old verify_*.sh runs discovered or used (taken from the raw logs). They are NEVER used as inputs: they only
# let this script print whether the circuit and inputs are unchanged since the old runs.
declare -A OLDVAL=(
  [merkle_8]=7028720585430303887570002302278980460894336162115285260509585927530919019891
  [merkle_16]=16583262526602274908326067473715682454713032735441436283661755515998944202415
  [merkle_32]=20423030625995436285279479924046495790834672715859007564257505760766364087270
  [poseidon_64]=12977603586150215176737170700933411671521376300841946324188299489382731017410
  [poseidon_256]=6625781724567783151019659453048597576755659058242974169987516206580194996227
  [poseidon_512]=5272706100675861572954429260300407996236585194829985617281545191578970831668
  [poseidon_1024]=12201746564020505244764431712123948954006357598207025395494458562047888457121
)

now()    { date +%s.%N; }
el()     { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.3f", b-a}'; }
hms()    { awk -v s="$1" 'BEGIN{printf "%02d:%02d:%02d", s/3600, (s%3600)/60, s%60}'; }
inner()  { echo "$1" | sed -n 's/^INNER \([0-9.]*\) RC.*/\1/p' | head -1; }
rcof()   { echo "$1" | sed -n 's/^INNER [0-9.]* RC \([0-9]*\).*/\1/p' | head -1; }
shuffle(){ awk -v seed="$1" 'BEGIN{srand(seed)} {print rand() "\t" $0}' | sort -n | cut -f2-; }
select_ids() { local id; for id in "$@"; do if [ -z "$ONLY" ] || [[ " $ONLY " == *" $id "* ]]; then echo "$id"; fi; done; }

C=zkp_bench; DXE=($([ "$ZK_MODE" = native ] && echo "ZBACKEND=$BACKEND ZFAST=$FAST ZTIMERS=$PWD/$TIMERS" || echo "-e ZOKRATES=$ZOKP -e ZBACKEND=$BACKEND -e ZFAST=$FAST -e ZTIMERS=/home/zokrates/zokrates_timers")); RUNARGS=(); STORAGE=local
CSV="$RES/results.csv"; DONE="$RES/done.list"
HEADER="family,parameter,constraints,replicate,compile_s,setup_s,witness_s,proof_s,verify_s,verify_passed,source_log,compile_inner_s,setup_inner_s,witness_inner_s,proof_inner_s,verify_inner_s,storage,visit_position,timestamp_utc,status"

cleanup() { [ "$ZK_MODE" = docker ] && docker rm -f zkp_bench zkp_ctl > /dev/null 2>&1; return 0; }
X() {        # run a command "inside": in the container (docker exec) or directly in the scratch folder (native)
  if [ "$ZK_MODE" = native ]; then ( cd "$NH" && env ZHOME="$NH" ZBASE="$NH/base" ZOKRATES="$ZOK_BIN" ZOKRATES_STDLIB="$ZOK_STD" "${DXE[@]}" "$@" )
  else docker exec "${DXE[@]}" "$C" "$@"; fi
}
alive() { [ "$ZK_MODE" = native ] || [ "$(docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null)" = true ]; }
trap cleanup EXIT
trap 'echo; echo "Interrupted. To continue this run:  RESUME=$RES bash run_phases_linux.sh$MODEARG"; exit 130' INT TERM

start_container() {
  if [ "$ZK_MODE" = native ]; then
    rm -rf "$NH"; mkdir -p "$NH/base" "$NH/w" || exit 1
    for f in zphase.sh zprep.sh; do cp "$f" "$NH/$f" || exit 1; done
    for f in circuits/*; do cp "$f" "$NH/base/" || exit 1; done
    return 0
  fi
  docker rm -f "$C" > /dev/null 2>&1
  docker run -d --name "$C" "${RUNARGS[@]}" --entrypoint sleep "$IMAGE" infinity > /dev/null \
    || { echo "Could not start the container $C. Is Docker running?"; exit 1; }
  docker exec "$C" mkdir -p base w || exit 1
  for f in zphase.sh zprep.sh; do docker cp "$f" "$C:/home/zokrates/$f" || exit 1; done
  for f in circuits/*; do docker cp "$f" "$C:/home/zokrates/base/" || exit 1; done
  docker cp "$TIMERS" "$C:/home/zokrates/zokrates_timers" || exit 1
  docker cp zok_wrap.sh "$C:/home/zokrates/zok_wrap.sh" || exit 1
  docker exec -u 0 "$C" chmod 755 /home/zokrates/zokrates_timers /home/zokrates/zok_wrap.sh || exit 1
  docker exec "$C" /home/zokrates/zokrates_timers --version || { echo "!!! The instrumented binary does not run in the container."; exit 1; }
}

capture_env() {
  {
    echo "instrumented binary: $(sha256sum "$TIMERS")"; ./"$TIMERS" --version 2>/dev/null; echo "back end: ${BACKEND:-ark (default)}"; echo "fast path (matrices cached at setup): ${FAST:-no}"
    echo "# run_phases_linux.sh mode=$MODE ZK_MODE=$ZK_MODE REPS=$REPS WARMUP=$WARMUP CONTROL=$CONTROL ONLY='$ONLY' started $(date -u +%FT%TZ) (host clock)"
    [ -n "${RESUME:-}" ] && echo "# RESUMED $(date -u +%FT%TZ)"
    echo "machine label: $(cat .machine 2>/dev/null)"
    capture_env_basic
    if [ "$ZK_MODE" = docker ]; then
      docker version 2>&1 | head -60
      docker image inspect "$IMAGE" --format 'image {{.Id}} created {{.Created}}' 2>/dev/null
      echo "# inside the container"
      docker exec "$C" bash -c 'zokrates --version; echo "binary sha256: $(sha256sum "$(command -v zokrates)" | cut -d" " -f1)"; echo "cpus: $(nproc)"; grep -m1 "model name" /proc/cpuinfo; free -m | sed -n 2p; uname -r' 2>&1
    else
      echo "# native ZoKrates"; "$ZOK_BIN" --version; echo "binary: $ZOK_BIN  sha256: $(zok_sha256 "$ZOK_BIN")  stdlib: $ZOK_STD"
    fi
  } >> "$RES/env.txt" 2>&1
}

prep_ids() {      # prepare every id in IDS inside the current container; READY_IDS = those that succeeded
  READY_IDS=()
  local id r c v
  for id in "${IDS[@]}"; do
    echo "--- prepare $id (${FAM[$id]} ${PAR[$id]})"
    r=$(X bash zprep.sh "$id" "${TYP[$id]}" "${P1[$id]}" "${P2[$id]}" 2>&1); r=${r//$'\r'/}
    echo "$r" | sed 's/^/    /'
    v=$(echo "$r" | sed -n 's/.*discovered expected \(value\|root\): *//p' | tail -1)
    if [ -n "$v" ] && [ -n "${OLDVAL[$id]:-}" ]; then
      if [ "$v" = "${OLDVAL[$id]}" ]; then echo "    same value as in the old log: circuit and inputs are unchanged"
      else echo "!!! DIFFERENT from the old log (${OLDVAL[$id]}): the circuit or its inputs differ from the old runs."; fi
    fi
    c=$(echo "$r" | sed -n 's/^READY //p' | tail -1)
    if [ -n "$c" ]; then CIRC[$id]=$c; READY_IDS+=("$id"); else echo "!!! preparation failed for $id: it will be skipped"; fi
  done
}

visit() {         # visit <id> <replicate> <position in pass>
  local id=$1 rep=$2 pos=$3 ph phases r t0 t1 rc cons="" passed="" status=OK
  local -A OT IT
  HWFAIL=0
  phases="compile setup witness proof verify"; [[ "${TYP[$id]}" == *_c ]] && phases="compile"
  for ph in $phases; do
    t0=$(now); r=$(X bash zphase.sh "w/$id" "$ph" "${CIRC[$id]}" 2>&1); t1=$(now)
    r=${r//$'\r'/}
    if echo "$r" | grep -qiE 'input/output error|read-only file system|no space left on device'; then HWFAIL=1; fi
    OT[$ph]=$(el "$t0" "$t1"); IT[$ph]=$(inner "$r"); rc=$(rcof "$r")
    echo "    --- $ph: host ${OT[$ph]} s, inside ${IT[$ph]:-?} s, exit code ${rc:-?}"
    echo "$r" | sed '1d' | sed 's/^/        /'
    case $ph in
      compile) cons=$(echo "$r" | sed -n 's/.*Number of constraints: *\([0-9]*\).*/\1/p' | head -1)
               if [ "$rc" != 0 ] || [ "$cons" != "${EXP[$id]}" ]; then status="COMPILE_FAILED_OR_WRONG_COUNT(got=${cons:-none},expected=${EXP[$id]})"; break; fi ;;
      setup)   if [ "$rc" != 0 ] || ! echo "$r" | grep -qi "setup completed\|proving key written"; then status=SETUP_FAILED; break; fi ;;
      witness) if [ "$rc" != 0 ] || ! echo "$r" | grep -q "Witness file written"; then status=WITNESS_FAILED; break; fi ;;
      proof)   if [ "$rc" != 0 ] || ! echo "$r" | grep -q "Proof written"; then status=PROOF_FAILED; break; fi ;;
      verify)  if [ "$rc" = 0 ] && echo "$r" | grep -q "PASSED"; then passed=True; else passed=False; status=VERIFY_FAILED; fi ;;
    esac
  done
  printf '"%s","%s",%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s"\n' \
    "${FAM[$id]}" "${PAR[$id]}" "$cons" "$rep" \
    "${OT[compile]:-}" "${OT[setup]:-}" "${OT[witness]:-}" "${OT[proof]:-}" "${OT[verify]:-}" "$passed" "raw_run.log" \
    "${IT[compile]:-}" "${IT[setup]:-}" "${IT[witness]:-}" "${IT[proof]:-}" "${IT[verify]:-}" \
    "$STORAGE" "$pos" "$(date -u +%FT%TZ)" "$status" >> "$CSV"
  echo ">>> $id replicate $rep: constraints=${cons:-?} status=$status | host c/s/w/p/v = ${OT[compile]:-}/${OT[setup]:-}/${OT[witness]:-}/${OT[proof]:-}/${OT[verify]:-} | inside = ${IT[compile]:-}/${IT[setup]:-}/${IT[witness]:-}/${IT[proof]:-}/${IT[verify]:-}"
}

run_passes() {    # run_passes <label> ; uses READY_IDS, CSV, DONE, C, DXE, STORAGE
  local label=$1 rep order pos id why n=${#READY_IDS[@]} total t_run=$(now)
  [ -f "$CSV" ] || echo "$HEADER" > "$CSV"
  total=$(( (REPS + WARMUP) * n ))
  for rep in $(seq $((1 - WARMUP)) "$REPS"); do
    order=$(printf '%s\n' "${READY_IDS[@]}" | shuffle $((rep + 10)))
    echo "pass $rep ($label): $(echo $order)" >> "$RES/order.txt"
    echo "pass $rep ($label) start $(date -u +%FT%TZ)  battery_status(2=AC)=$(ac_state)  cpu_clock_mhz=$(cpu_mhz)  host_free_gb=$(host_free_gb)  c_free_gb=$(free_gb_of /) load=$(cut -d' ' -f1-3 /proc/loadavg) steal_jiffies=$(awk '/^cpu /{print $9}' /proc/stat)" >> "$RES/pass_log.txt"
    echo; echo "================ pass $rep of $REPS$([ "$rep" = 0 ] && echo ' (warm-up)') [$label] ================"
    pos=0
    for id in $order; do
      pos=$((pos + 1))
      if grep -qx "$id $rep" "$DONE" 2>/dev/null; then echo "(skip: $id replicate $rep already done)"; continue; fi
      if why=$(disk_low); then      # Docker's virtual disk grows while the circuits run; stop before a full drive damages a measurement
        echo "!!! $why. A full drive makes Docker fail with Input/output error. Stopping before a measurement is damaged."
        echo "!!! Free disk space, then continue with:  RESUME=$RES bash run_phases_linux.sh$MODEARG"; exit 1
      fi
      echo; echo "[$label pass $rep, circuit $pos/$n, elapsed $(hms "$(el "$t_run" "$(now)")")] $id: ${FAM[$id]} ${PAR[$id]}"
      visit "$id" "$rep" "$pos"
      if [ "${HWFAIL:-0}" = 1 ] || ! alive; then
        { echo "# power events at the failure ($(date -u +%FT%TZ)); Id 42 = went to sleep, 107 = woke up"; power_events 14; } >> "$RES/power_events.txt" 2>&1
        echo "!!! The container stopped or the disk failed (Input/output error). Usual causes: the machine was suspended or recycled, the disk is nearly full, or an out-of-memory kill (ECDSA, RSA-4096 need about 4.5 GiB)."
        echo "!!! This visit is NOT marked done and will be repeated. Free disk space, restart Docker if it stopped, then continue with:  RESUME=$RES bash run_phases_linux.sh$MODEARG"; exit 1
      fi
      echo "$id $rep" >> "$DONE"
    done
    echo "pass $rep ($label) end   $(date -u +%FT%TZ)  battery_status(2=AC)=$(ac_state)  cpu_clock_mhz=$(cpu_mhz)  host_free_gb=$(host_free_gb)  c_free_gb=$(free_gb_of /) load=$(cut -d' ' -f1-3 /proc/loadavg) steal_jiffies=$(awk '/^cpu /{print $9}' /proc/stat)" >> "$RES/pass_log.txt"
    [ -n "${AFTER_PASS_HOOK:-}" ] && { eval "$AFTER_PASS_HOOK"; } > /dev/null 2>&1      # between passes, outside every timed region
  done
}

# ---------------------------------------------------------------- start
if [ "$ZK_MODE" = docker ]; then docker info > /dev/null 2>&1 || { echo "Docker is not running (ZK_MODE=docker). Start it, or use ZK_MODE=native after  bash check_setup_linux.sh"; exit 1; }
else "$ZOK_BIN" --version > /dev/null 2>&1 || { echo "ZoKrates binary not found or not runnable at $ZOK_BIN. Run  bash check_setup_linux.sh  first."; exit 1; }; fi
for f in envlib_linux.sh zphase.sh zprep.sh circuits/poseidon_chain.zok circuits/merkle_poseidon.zok circuits/rsa_accumulator_param.zok circuits/rsa2048_verify.zok circuits/rsa2048_args.txt circuits/ecdsa_verify.zok circuits/ecdsa_args.txt circuits/rsa1024_verify.zok circuits/rsa1024_args.txt circuits/rsa3072_verify.zok circuits/rsa3072_args.txt circuits/rsa4096_verify.zok circuits/rsa4096_args.txt circuits/sha256_hash_circuit.zok circuits/sha256_args_ecc.txt circuits/sha256_args_rsa.txt circuits/synth_full_100k.zok circuits/synth_full_300k.zok circuits/synth_full_args.txt circuits/synth_bool_100k.zok circuits/synth_bool_300k.zok circuits/synth_bool_args.txt; do
  [ -f "$f" ] || { echo "Missing file $f. Run this from the extracted folder."; exit 1; }
done
echo "Run folder: $RES   mode=$MODE REPS=$REPS WARMUP=$WARMUP CONTROL=$CONTROL ONLY='${ONLY}'"
BAT=$(ac_state)
echo "battery status now (2 = on AC power, 1 = on battery): $BAT"
echo "mode: $ZK_MODE   cpus: $(nproc)   $(cpu_name)"
if [ "$BAT" = 1 ] && [ "$MODE" != quick ] && [ "$MODE" != ecdsaquick ] && [ "$MODE" != rsarealquick ] && [ "$MODE" != synthquick ] && [ -z "${ALLOW_BATTERY:-}" ]; then
  echo
  echo "!!! STOP: Windows reports that this laptop is running on BATTERY. Timings on battery cannot be compared with runs made on AC (9 Nov)."
  echo "!!! Plug in the original charger, wait 30 seconds, and start the same command again."
  echo "!!! (To measure on battery on purpose:  ALLOW_BATTERY=1 bash run_remeasure.sh$MODEARG)"
  exit 1
fi
if [ "$MODE" != quick ] && [ "$MODE" != ecdsaquick ] && [ "$MODE" != rsarealquick ] && [ "$MODE" != synthquick ] && [ -z "${RESUME:-}" ] && [ -z "${NOWAIT:-}" ]; then
  echo "Before this starts: plug in the charger, set Settings > System > Power > Power mode to Best performance, set sleep to Never"
  echo "while plugged in, close other programs, and leave the laptop alone. Starting in 15 s (Ctrl-C to cancel)."; sleep 15
fi

pending_filter() {   # prints those ids (from the arguments) that still have a visit not recorded in $DONE
  local id rep
  for id in "$@"; do
    for rep in $(seq $((1 - WARMUP)) "$REPS"); do
      if ! grep -qx "$id $rep" "$DONE" 2>/dev/null; then echo "$id"; break; fi
    done
  done
}

IDS=($(select_ids "${ALL_IDS[@]}"))
[ ${#IDS[@]} -gt 0 ] || { echo "No circuits selected (check ONLY)."; exit 1; }
STORAGE=local; C=zkp_bench; DXE=($([ "$ZK_MODE" = native ] && echo "ZBACKEND=$BACKEND ZFAST=$FAST ZTIMERS=$PWD/$TIMERS" || echo "-e ZOKRATES=$ZOKP -e ZBACKEND=$BACKEND -e ZFAST=$FAST -e ZTIMERS=/home/zokrates/zokrates_timers")); RUNARGS=(); CSV="$RES/results.csv"; DONE="$RES/done.list"
IDS=($(pending_filter "${IDS[@]}"))
if [ ${#IDS[@]} -gt 0 ]; then
  start_container
  capture_env
  prep_ids
  [ ${#READY_IDS[@]} -gt 0 ] || { echo "Nothing could be prepared."; exit 1; }
  run_passes main
else
  echo "All main visits are already recorded in $RES."
fi

# ---------------------------------------------------------------- control: the old method (Windows bind mount), a few circuits
if [ "$CONTROL" = 1 ] && [ "$ZK_MODE" = docker ]; then
  probe=$(mktemp -d "$PWD/probe.XXXXXX") && chmod 777 "$probe" && docker run --rm -v "$probe:/bind" --entrypoint sh "$IMAGE" -c 'touch /bind/t' > /dev/null 2>&1 && [ -e "$probe/t" ] || { echo "bind mounts do not work on this host: control skipped"; CONTROL=0; }
  rm -rf "$probe"
fi
if [ "$CONTROL" = 1 ] && [ "$ZK_MODE" = docker ]; then
  echo; echo "================ CONTROL: same circuits on a bind-mounted host folder ================"
  docker rm -f "$C" > /dev/null 2>&1
  BINDDIR="$RES/bindctl"; mkdir -p "$BINDDIR"; chmod 777 "$BINDDIR"
  BINDHOST=$(cd "$BINDDIR" && { pwd -W 2>/dev/null || pwd; })
  STORAGE=bindmount; C=zkp_ctl; RUNARGS=(-v "$BINDHOST:/bind"); DXE=(-e ZHOME=/bind -e ZBASE=/home/zokrates/base)
  CSV="$RES/results_bind_control.csv"; DONE="$RES/done_control.list"
  IDS=($(select_ids $CONTROL_IDS))
  IDS=($(pending_filter "${IDS[@]}"))
  if [ ${#IDS[@]} -gt 0 ]; then
    start_container
    { echo "# control container: bind mount $BINDHOST -> /bind"; } >> "$RES/env.txt"
    prep_ids
    [ ${#READY_IDS[@]} -gt 0 ] && run_passes control
  else
    echo "All control visits are already recorded."
  fi
  docker rm -f "$C" > /dev/null 2>&1
  rm -rf "$BINDDIR" 2>/dev/null
fi

echo; echo "================ finished $(date -u +%FT%TZ) ================"
for f in "$RES/results.csv" "$RES/results_bind_control.csv"; do
  [ -f "$f" ] && awk -F, -v f="$f" 'NR>1{ if ($NF=="\"OK\"") ok++; else bad++ } END{printf "%s: %d rows OK, %d rows with a problem\n", f, ok, bad}' "$f"
done
{ echo "# power events at the end ($(date -u +%FT%TZ)); Id 42 = went to sleep, 107 = woke up"; power_events 14; } >> "$RES/power_events.txt" 2>&1
echo "Results are in $RES (results.csv, results_bind_control.csv if the control ran, env.txt, order.txt, pass_log.txt, raw_run.log); bash pack_results_linux.sh packs them."
nbat=$(grep -c 'battery_status(2=AC)=1' "$RES/pass_log.txt" 2>/dev/null || true)
if [ "${nbat:-0}" -gt 0 ]; then echo "WARNING: $nbat pass records in pass_log.txt say the laptop was on battery. Do not compare this run with runs made on AC."; fi
python3 phases_extract.py "$RES" || echo "(phases_extract.py could not run here; send the folder anyway)"
