#!/bin/bash
# Container side. Prepares one configuration folder under $ZHOME/w/<id> the way the original verify_*.sh scripts did
# (copy the base circuit, set its parameters with sed, discover the REAL expected value with a return-only variant),
# but inside the container. Nothing here is timed.
# usage: bash zprep.sh <id> <type> [p1] [p2]
#   types: poseidon <rounds> | merkle <depth> | rsa <exp_bits> <reps> | rsa2048 | rsareal <key bits> | sha <ecc|rsa> | synth <full|bool> <100k|300k> | ecdsa | eddsa <sha256|poseidon>
#          (suffix _c = compile-only: no inputs)
# Prints "READY <circuit file>" on success, "PREP_FAIL ..." otherwise.
H=${ZHOME:-/home/zokrates}; B=${ZBASE:-/home/zokrates/base}
ZOK=${ZOKRATES:-$(command -v zokrates || echo /home/zokrates/zokrates)}
id=$1; type=$2; p1=$3; p2=$4
d="$H/w/$id"; rm -rf "$d"; mkdir -p "$d" && cd "$d" || { echo "PREP_FAIL cannot create $d"; exit 0; }

# disc <return-only circuit> <witness args...>: compile it, compute a witness with --verbose, print the returned value
disc() {
  local f=$1; shift
  mkdir -p ro; cp "$f" ro/
  ( cd ro && "$ZOK" compile -i "$f" > compile.log 2>&1 && "$ZOK" compute-witness --verbose -a "$@" > witness.log 2>&1 )
  echo "    return-only variant: $(grep -h 'Number of constraints' ro/compile.log)" >&2
  grep -oE '\["[0-9]+"\]' ro/witness.log 2>/dev/null | grep -oE '[0-9]+' | head -1
}

case "${type%_c}" in
  poseidon)
    c="poseidon_chain_${p1}.zok"; cp "$B/poseidon_chain.zok" "$c" || { echo "PREP_FAIL missing base circuit"; exit 0; }
    sed -i "s/const u32 ROUNDS = 64;/const u32 ROUNDS = $p1;/" "$c"
    grep -n "ROUNDS =" "$c"
    if [ "$type" = poseidon ]; then
      ro="poseidon_chain_${p1}_returnonly.zok"; cp "$c" "$ro"
      sed -i 's/assert(value == expected);/\/\/ assert(value == expected); \/\/ return-only variant/' "$ro"
      grep -q "// assert(value == expected)" "$ro" || { echo "PREP_FAIL sed did not comment the assert line"; exit 0; }
      v=$(disc "$ro" 12345 0)
      [ -n "$v" ] || { echo "PREP_FAIL could not discover the expected value"; exit 0; }
      echo "12345 $v" > args.txt; echo "    discovered expected value: $v"
    fi ;;
  merkle)
    c="merkle_poseidon_${p1}.zok"; cp "$B/merkle_poseidon.zok" "$c" || { echo "PREP_FAIL missing base circuit"; exit 0; }
    sed -i "s/const u32 DEPTH = 16;/const u32 DEPTH = $p1;/" "$c"
    grep -n "DEPTH =" "$c"
    if [ "$type" = merkle ]; then
      PE=$(printf '0 %.0s' $(seq 1 "$p1"))     # all-zero path elements and all-false directions, as in verify_merkle.sh
      ro="merkle_poseidon_${p1}_returnonly.zok"; cp "$c" "$ro"
      sed -i 's/assert(computed_hash == expected_root);/\/\/ assert(computed_hash == expected_root); \/\/ return-only variant/' "$ro"
      grep -q "// assert(computed_hash == expected_root)" "$ro" || { echo "PREP_FAIL sed did not comment the assert line"; exit 0; }
      v=$(disc "$ro" 12345 $PE $PE 0)
      [ -n "$v" ] || { echo "PREP_FAIL could not discover the expected root"; exit 0; }
      echo "12345 $PE $PE $v" > args.txt; echo "    discovered expected root: $v"
    fi ;;
  rsa)
    c="rsa_accumulator_${p1}_${p2}.zok"; cp "$B/rsa_accumulator_param.zok" "$c" || { echo "PREP_FAIL missing base circuit"; exit 0; }
    sed -i "s/const u32 EXP_BITS = [0-9]*;/const u32 EXP_BITS = $p1;/" "$c"
    sed -i "s/const u32 REPS = [0-9]*;/const u32 REPS = $p2;/" "$c"
    grep -nE "const u32 (EXP_BITS|REPS)" "$c"
    [ "$type" = rsa ] && echo "12345 1 1 2 1" > args.txt ;;     # the same fixed witness as verify_rsa.sh
  rsa2048)
    c="rsa2048_verify.zok"; cp "$B/rsa2048_verify.zok" "$c" && cp "$B/rsa2048_args.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  rsareal)   # real RSA-<p1> verifier: circuits/rsa<p1>_verify.zok and circuits/rsa<p1>_args.txt
    c="rsa${p1}_verify.zok"; cp "$B/$c" "$c" && cp "$B/rsa${p1}_args.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  sha)       # SHA-256 baseline circuit (repository hash_circuit.zok); p1 = ecc | rsa chooses the witness
    c="sha256_hash_circuit.zok"; cp "$B/$c" "$c" && cp "$B/sha256_args_${p1}.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  synth)     # synthetic mechanism circuits: p1 = full | bool (witness values full-width | 0/1), p2 = 100k | 300k (constraints)
    c="synth_${p1}_${p2}.zok"; cp "$B/$c" "$c" && cp "$B/synth_${p1}_args.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  eddsa)     # BabyJubJub EdDSA verifiers: p1 = sha256 (standard library) | poseidon (variant); fixed valid signatures in circuits/eddsa_<p1>_args.txt
    c="eddsa_${p1}_verify.zok"; cp "$B/$c" "$c" && cp "$B/eddsa_${p1}_args.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  ecdsa)
    c="ecdsa_verify.zok"; cp "$B/ecdsa_verify.zok" "$c" && cp "$B/ecdsa_args.txt" args.txt || { echo "PREP_FAIL missing base circuit"; exit 0; } ;;
  *) echo "PREP_FAIL unknown type $type"; exit 0 ;;
esac
echo "READY $c"
