#!/bin/bash
# Packs the result folders of THIS machine into one zip named after the CPU label: zkp_v4_results_<label>.zip
# (quick-check folders ending in _quick are left out). Run it in the package folder on each machine.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")" || exit 1
source ./envlib.sh
TAG=$(cat .machine 2>/dev/null); [ -n "$TAG" ] || TAG=$(machine_tag)
{ echo "label: $TAG"; capture_env_basic; } > "machine_${TAG}.txt" 2>&1
items=()
for d in native_* results_* memory_*; do [ -d "$d" ] && [[ "$d" != *_quick ]] && items+=("$d"); done
[ ${#items[@]} -gt 0 ] || { echo "No native_*, results_* or memory_* folder found here. Run the steps first."; exit 1; }
items+=("machine_${TAG}.txt")
OUT="zkp_v4_results_${TAG}.zip"
echo "Packing: ${items[*]}"
if command -v powershell.exe > /dev/null 2>&1; then
  list=$(printf "'%s'," "${items[@]}"); list=${list%,}
  powershell.exe -NoProfile -Command "Compress-Archive -Path $list -DestinationPath '$OUT' -Force"
else
  OUT="${OUT%.zip}.tgz"; tar czf "$OUT" "${items[@]}"
fi
if [ -f "$OUT" ]; then echo "Done: $OUT  ($(du -h "$OUT" | cut -f1)). Attach this file."; else echo "!!! packing failed"; exit 1; fi
