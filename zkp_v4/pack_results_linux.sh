#!/bin/bash
# Packs the result folders of THIS machine into zkp_v4_results_<label>.zip (quick-check folders ending in _quick are left out).
cd "$(dirname "$0")" || exit 1
source ./envlib_linux.sh
export ZK_MODE=${ZK_MODE:-$(cat .zkmode 2> /dev/null)}
TAG=$(cat .machine 2> /dev/null); [ -n "$TAG" ] || TAG=$(machine_tag)
{ echo "label: $TAG"; capture_env_basic; } > "machine_${TAG}.txt" 2>&1
items=()
for d in native_* results_* memory_*; do [ -d "$d" ] && [[ "$d" != *_quick ]] && items+=("$d"); done
[ ${#items[@]} -gt 0 ] || { echo "No native_*, results_* or memory_* folder found here. Run the steps first."; exit 1; }
items+=("machine_${TAG}.txt"); [ -f run_all.out ] && items+=(run_all.out)
OUT="zkp_v4_results_${TAG}.zip"
echo "Packing: ${items[*]}"
if command -v zip > /dev/null 2>&1; then rm -f "$OUT"; zip -rq "$OUT" "${items[@]}"; else OUT="${OUT%.zip}.tgz"; tar czf "$OUT" "${items[@]}"; fi
if [ -f "$OUT" ]; then echo "Done: $OUT  ($(du -h "$OUT" | cut -f1)). This is the file to send back."; else echo "!!! packing failed"; exit 1; fi
