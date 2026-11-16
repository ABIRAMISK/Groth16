#!/bin/bash
# Structure extractor driver. For every configuration in analysis/configs.tsv: prepare the circuit exactly like the harness (zkp_v4/zprep.sh),
# compile it with ZoKrates 0.8.7, compute the witness, extract the structure features with analysis/r1cs_features3.py and delete the big files.
#
# usage, from anywhere:   ZOKRATES=/path/to/zokrates ZOKRATES_STDLIB=/path/to/stdlib bash analysis/struct_driver.sh [ID ...]
#   ZOKRATES         the zokrates 0.8.7 binary (default: zokrates on the PATH)
#   ZOKRATES_STDLIB  the stdlib folder of the same release (required)
#   ZHOME            scratch folder for the compiled circuits, several GB for the largest ones (default /tmp/zkp_struct)
#   ID ...           optional configuration ids to run (default: all 28)
# Output: analysis/work/features3.jsonl. Compare it with the shipped analysis/features3.jsonl: every field is deterministic except "secs" (wall-clock seconds).
ROOT=$(cd "$(dirname "$0")/.." && pwd); P=$ROOT/zkp_v4; W=$ROOT/analysis/work
export ZHOME=${ZHOME:-/tmp/zkp_struct} ZBASE=$P/circuits
export ZOKRATES=${ZOKRATES:-zokrates}
export ZOKRATES_STDLIB=${ZOKRATES_STDLIB:?set ZOKRATES_STDLIB to the stdlib folder of the ZoKrates 0.8.7 release}
mkdir -p "$W"; OUT=$W/features3.jsonl; : > "$OUT"
want=" $* "
while IFS=$'\t' read -r id fam par typ ncon p1 p2; do
  if [ $# -gt 0 ] && [[ "$want" != *" $id "* ]]; then continue; fi
  t0=$(date +%s)
  r=$(bash "$P/zprep.sh" "$id" "$typ" "$p1" "$p2" 2>/dev/null | tail -1)
  case "$r" in READY*) ;; *) echo "{\"id\":\"$id\",\"error\":\"prep: $r\"}" >> "$OUT"; echo "$id PREP FAIL $r"; continue;; esac
  cd "$ZHOME/w/$id" || continue
  circ=${r#READY }
  timeout 3000 "$ZOKRATES" compile -i "$circ" > compile.log 2>&1 || { echo "{\"id\":\"$id\",\"error\":\"compile\"}" >> "$OUT"; echo "$id COMPILE FAIL"; cd /; continue; }
  if [ -s args.txt ]; then timeout 3000 "$ZOKRATES" compute-witness -a $(cat args.txt) > witness.log 2>&1 || echo "$id WITNESS FAIL"; fi
  feat=$(python3 -I "$ROOT/analysis/r1cs_features3.py" . --check 200 2>err.log) || { echo "{\"id\":\"$id\",\"error\":\"features: $(tail -1 err.log)\"}" >> "$OUT"; echo "$id FEATURES FAIL"; cd /; continue; }
  echo "{\"id\":\"$id\",\"family\":\"$fam\",\"type\":\"$typ\",\"expected_constraints\":$ncon,\"secs\":$(( $(date +%s) - t0 )),\"f\":$feat}" >> "$OUT"
  echo "$id done $(( $(date +%s) - t0 ))s"
  cd /; rm -rf "$ZHOME/w/$id"
done < "$ROOT/analysis/configs.tsv"
echo ALLDONE
