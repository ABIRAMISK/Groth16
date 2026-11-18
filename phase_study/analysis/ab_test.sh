#!/bin/bash
# A/B test of generate-proof: original instrumented binary (A) against the fixed binary (B), same compiled program,
# same proving key, same witness; passes alternate A,B,A,B,... Proofs of B are verified with A's verify.
# usage: bash ab_test.sh <reps> <id> [<id> ...]
S=${S:?set S to the working folder}
REPO=$S/groth16_live/repo
A=${A:-$S/zk/src/target/release/zokrates}
B=${B:-$S/zk/target_fix/release/zokrates}
export ZOKRATES=$A ZOKRATES_STDLIB=$S/zk/src/zokrates_stdlib/stdlib ZHOME=$S/zk/work_ab ZBASE=$REPO/zkp_v4/circuits
OUT=${OUT:-$S/zk/ab_out}; mkdir -p "$OUT" "$ZHOME"
reps=$1; shift
for id in "$@"; do
  line=$(awk -F'\t' -v i="$id" '$1==i' "$REPO/analysis/configs.tsv")
  typ=$(echo "$line" | cut -f4); p1=$(echo "$line" | cut -f6); p2=$(echo "$line" | cut -f7)
  if [ -z "$line" ]; then  # EdDSA circuits of the frozen test
    mkdir -p "$ZHOME/w/$id"; v=${id#eddsa_}; cp "$S/zk/kit3/zkp_eddsa/circuits/eddsa_${v}_verify.zok" "$ZHOME/w/$id/"; cp "$S/zk/kit3/zkp_eddsa/circuits/eddsa_${v}_args.txt" "$ZHOME/w/$id/args.txt"; r="READY eddsa_${v}_verify.zok"
  else
    r=$(bash "$REPO/zkp_v4/zprep.sh" "$id" "$typ" "$p1" "$p2" 2>/dev/null | tail -1)
  fi
  case "$r" in READY*) ;; *) echo "$id PREP FAIL $r"; continue;; esac
  cd "$ZHOME/w/$id" || continue
  "$A" compile -i "${r#READY }" > compile.log 2>&1 && "$A" setup > setup.log 2>&1 && "$A" compute-witness -a $(cat args.txt) > witness.log 2>&1 || { echo "$id PIPELINE FAIL"; continue; }
  : > "$OUT/$id.ab"
  for rep in $(seq 0 "$reps"); do
    for v in A B; do
      bin=$A; [ $v = B ] && bin=$B
      if [ $v = B ] && [ -n "$FASTB" ]; then export ZOK_MATRIX_CACHE=$PWD/matrices.bin; else unset ZOK_MATRIX_CACHE; fi
      t0=$(date +%s.%N); "$bin" generate-proof > proof.log 2> zkt.err || { echo "$id $v PROOF FAIL"; tail -3 zkt.err; break 2; }; t1=$(date +%s.%N)
      ok=$("$A" verify 2>&1 | tail -1)
      echo "$id $rep $v wall $(echo "$t1-$t0"|bc) verify=${ok// /_}" >> "$OUT/$id.ab"
      grep '^ZKT' zkt.err | sed "s/^ZKT/$id $rep $v/" >> "$OUT/$id.ab"
    done
  done
  unset ZOK_MATRIX_CACHE; [ -f matrices.bin ] && echo "$id cache size $(stat -c %s matrices.bin) bytes" >> "$OUT/$id.ab"
  echo "$id done: $(grep -c 'verify=PASSED' "$OUT/$id.ab") of $(grep -c ' wall ' "$OUT/$id.ab") proofs verified"
  cd /; rm -rf "$ZHOME/w/$id"
done
echo ALLDONE
