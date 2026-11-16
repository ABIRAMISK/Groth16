#!/bin/bash
# LINUX VARIANT (Codespaces, Colab, any Linux machine), derived from run_memory_profile.sh by make_linux_scripts.py. ZK_MODE=docker|native as in run_remeasure_linux.sh.
# Peak memory and CPU time per phase of the ZoKrates process, for every circuit of run_remeasure.sh: ONE untimed visit per circuit.
# Read from /proc inside the container (zprofile.sh): peak resident set size (VmHWM) and CPU time (utime+stime).
# Time is NOT taken from this run (the polling disturbs it); the timings come from run_remeasure.sh.
#   bash run_memory_profile.sh                 all circuits, about 15 minutes
#   ONLY="rsa1024real sha256_ecc" bash run_memory_profile.sh     selected circuits
#   RESUME=memory_2026... bash run_memory_profile.sh             continue an interrupted run
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")" || exit 1
ZK_MODE=${ZK_MODE:-$(cat .zkmode 2>/dev/null)}; ZK_MODE=${ZK_MODE:-docker}; export ZK_MODE
NH=${NATIVE_HOME:-/tmp/zk_native}; ZOK_BIN=${ZOK_BIN:-$PWD/zokrates_bin/zokrates}; ZOK_STD=${ZOK_STD:-$PWD/zokrates_bin/stdlib}
source ./envlib_linux.sh
IMAGE=${IMAGE:-zokrates/zokrates:0.8.7}; ONLY=${ONLY:-}; C=zkp_mem
RES=${RESUME:-memory_$(date +%Y%m%d_%H%M%S)${MEM_SUFFIX:-}}; mkdir -p "$RES" || exit 1
exec > >(tee -a "$RES/raw_run.log") 2>&1
if [ "$ZK_MODE" = docker ]; then docker info > /dev/null 2>&1 || { echo "Docker is not running (ZK_MODE=docker)."; exit 1; }
else "$ZOK_BIN" --version > /dev/null 2>&1 || { echo "ZoKrates binary not found at $ZOK_BIN. Run  bash check_setup_linux.sh  first."; exit 1; }; fi
BAT=$(ac_state)
if [ "$BAT" = 1 ] && [ -z "${ALLOW_BATTERY:-}" ]; then echo "!!! STOP: the laptop is on BATTERY. Plug in the charger and start again."; exit 1; fi
eval "$(sed -n '/^CONFIGS=(/,/^)/p' run_remeasure_linux.sh)"          # the same circuit list as the timing session
CSV="$RES/memory_profile.csv"; DONE="$RES/done.list"
[ -f "$CSV" ] || echo 'id,family,parameter,constraints,phase,wall_s,peak_rss_mib,cpu_s,cpu_cores,polls,exit_code,timestamp_utc' > "$CSV"
{ capture_env_basic; echo "# run_memory_profile.sh ONLY='$ONLY'"; } >> "$RES/env.txt" 2>&1
cleanup() { [ "$ZK_MODE" = docker ] && docker rm -f "$C" > /dev/null 2>&1; return 0; }
DXE=()
X() { if [ "$ZK_MODE" = native ]; then ( cd "$NH" && env ZHOME="$NH" ZBASE="$NH/base" ZOKRATES="$ZOK_BIN" ZOKRATES_STDLIB="$ZOK_STD" "$@" ); else docker exec "$C" "$@"; fi; }
alive() { [ "$ZK_MODE" = native ] || [ "$(docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null)" = true ]; }
trap cleanup EXIT
trap 'echo; echo "Interrupted. To continue:  RESUME=$RES bash run_memory_profile_linux.sh"; exit 130' INT TERM
if [ "$ZK_MODE" = native ]; then
  rm -rf "$NH"; mkdir -p "$NH/base" "$NH/w" || exit 1
  for f in zprofile.sh zprep.sh; do cp "$f" "$NH/$f" || exit 1; done
  for f in circuits/*; do cp "$f" "$NH/base/" || exit 1; done
else
  docker rm -f "$C" > /dev/null 2>&1
  docker run -d --name "$C" --entrypoint sleep "$IMAGE" infinity > /dev/null || { echo "Could not start the container. Is Docker running?"; exit 1; }
  docker exec "$C" mkdir -p base w || exit 1
  for f in zprofile.sh zprep.sh; do docker cp "$f" "$C:/home/zokrates/$f" || exit 1; done
  for f in circuits/*; do docker cp "$f" "$C:/home/zokrates/base/" || exit 1; done
fi
echo "Run folder: $RES"
for line in "${CONFIGS[@]}"; do
  IFS='|' read -r id fam par typ exp p1 p2 <<< "$line"
  if [ -n "$ONLY" ] && [[ " $ONLY " != *" $id "* ]]; then continue; fi
  if grep -qx "$id" "$DONE" 2>/dev/null; then echo "(skip $id: done)"; continue; fi
  echo; echo "=== $id: $fam $par"
  r=$(X bash zprep.sh "$id" "$typ" "$p1" "$p2" 2>&1); r=${r//$'\r'/}
  cfile=$(echo "$r" | sed -n 's/^READY //p' | tail -1)
  if [ -z "$cfile" ]; then echo "!!! preparation failed for $id: skipped"; echo "$r" | tail -3; continue; fi
  phases="compile setup witness proof verify"; [[ "$typ" == *_c ]] && phases="compile"
  cons=""
  for ph in $phases; do
    r=$(X bash zprofile.sh "w/$id" "$ph" "$cfile" 2>&1); r=${r//$'\r'/}
    pl=$(echo "$r" | grep -m1 '^PROFILE ')
    [ "$ph" = compile ] && cons=$(echo "$r" | sed -n 's/.*Number of constraints: *\([0-9]*\).*/\1/p' | head -1)
    wall=$(echo "$pl" | sed -n 's/.* wall=\([0-9.]*\).*/\1/p'); hwm=$(echo "$pl" | sed -n 's/.* hwm_kib=\([0-9]*\).*/\1/p')
    tk=$(echo "$pl" | sed -n 's/.* cpu_ticks=\([0-9]*\).*/\1/p'); ck=$(echo "$pl" | sed -n 's/.* clk_tck=\([0-9]*\).*/\1/p')
    np=$(echo "$pl" | sed -n 's/.* polls=\([0-9]*\).*/\1/p'); rc=$(echo "$pl" | sed -n 's/.* rc=\([0-9]*\).*/\1/p')
    row=$(awk -v w="${wall:-0}" -v h="${hwm:-0}" -v t="${tk:-0}" -v k="${ck:-100}" 'BEGIN{cs=t/k; printf "%.3f,%.1f,%.2f,%.2f", w, h/1024, cs, (w>0? cs/w : 0)}')
    echo "    $ph: wall/peakMiB/cpu_s/cores = $row  polls=${np:-?} rc=${rc:-?}"
    printf '"%s","%s","%s",%s,%s,%s,%s,%s,%s,%s\n' "$id" "$fam" "$par" "${cons:-}" "$ph" "$row" "${np:-}" "${rc:-}" "$(date -u +%FT%TZ)" >> "$CSV"
    if [ "${rc:-1}" != 0 ]; then echo "!!! $ph failed for $id (exit code ${rc:-?}); remaining phases skipped"; echo "$r" | sed '1d' | tail -5; break; fi
  done
  echo "$id" >> "$DONE"
  X rm -rf "w/$id" > /dev/null 2>&1                 # keep the container's disk use small (ECDSA keeps 0.9 GB)
  if ! alive; then
    echo "!!! The container stopped (out of memory is the usual reason). Restart Docker and continue with:  RESUME=$RES bash run_memory_profile_linux.sh"; exit 1
  fi
done
echo; echo "================ finished $(date -u +%FT%TZ): $CSV ================"
