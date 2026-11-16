# RSA-2048 signature verification in a ZoKrates circuit

A real (not surrogate) circuit that checks an RSA-2048 PKCS#1 v1.5 / SHA-256 signature with e = 65537,
written for ZoKrates 0.8.7, Groth16, BN254, so it can sit next to the Poseidon and Merkle circuits in the paper.

**Statement proved:** there is a signature `s <= n` with `s^65537 = EM (mod n)`, where `EM` is the PKCS#1 v1.5
encoding of the public SHA-256 digest (RFC 8017, RSASSA-PKCS1-v1_5-VERIFY).

## What was measured (compile-only counts are exact and machine independent)

| item | value |
|---|---|
| R1CS constraints, `zokrates compile` with default flags | **153,484** |
| public inputs | modulus `n` (17 limbs), digest (3 limbs: 121 + 121 + 14 bits) |
| private inputs | signature `s`, `d = n - s`, quotients and remainders of the 17 modular multiplications (595 values in all) |
| end-to-end Groth16 check (setup, witness, prove, verify) | verify **PASSED** (run on a 2-core cloud VM, so its timings are not for the paper) |

## How the arithmetic works

A 2048-bit number is 17 limbs of 121 bits, each limb one BN254 scalar-field element (17 limbs cover 2048 bits, and all sums of limb
products stay below 2^248, well under half of the 254-bit prime). `s^65537` is 16 squarings and 1 multiplication. Each modular
multiplication is checked as `a*b = q*n + r` over the integers: limb products are formed in the field, then a carry chain is
verified with every carry range-checked to 127 bits. Every prover-supplied limb is range-checked to 121 bits. `s <= n` is
checked with a ripple-carry adder (`s + d = n`, boolean carries). The last remainder is the encoded message, built from
constants and the digest, so equality with `EM` is exact (no reduction needed).

## Constraint formula, reproduced exactly on the compiler

`R(L) = L + 2` constraints per range check of an L-bit value (L booleans, 1 recomposition, 1 assert; see note 1).

| part | count | constraints |
|---|---|---|
| limb range checks (`s`, `d`, `ql`, 16 `q`, 16 `r`: 35 x 17 limbs) | 595 x R(121) | 73,185 |
| digest range checks (121, 121, 14 bits) | 2 x R(121) + R(14) | 262 |
| `s <= n` adder | 17 booleans + 1 final assert | 18 |
| 17 modular-multiplication identities | 17 x (2K^2 + (2K-2) x R(127) + 1) = 17 x (578 + 4,128 + 1) | 80,019 |
| **total** | | **153,484** |

One full 2048-bit modular multiplication, including range-checked quotient and remainder, costs 4,707 + 34 x 123 = 8,889 constraints.

The formula was checked by removing parts of the circuit (the ablations below are also the mutants used for soundness tests):

| circuit | predicted | compiled |
|---|---|---|
| full | 153,484 | 153,484 |
| no `s <= n` check | 153,484 - 18 = 153,466 | 153,466 |
| no range checks on `q`, `r` | 153,484 - 16 x 34 x 123 = 86,572 | 86,572 |
| no carry range checks | 153,484 - 17 x 32 x 129 = 83,308 | 83,308 |
| no final zero-carry assert (also drops the 2 top-coefficient products) | 153,484 - 17 x 3 = 153,433 | 153,433 |

## Correctness and soundness tests (`results/test_report.txt`)

* Two real RSA-2048 keys, signatures made by the `cryptography` library, accepted by its own verifier and by this circuit.
* Ten tampered or forged inputs are rejected: flipped digest bit, signature + 1, wrong modulus, `s + n` (two encodings),
  out-of-range quotient limb, out-of-range remainder limb, quotient off by one, a forgery whose quotients are correct only
  modulo the BN254 prime, and a signature on `EM + 2^3872` with the last quotient adjusted so the integer identity is off by
  exactly `2^3872`.
* Four deliberately weakened copies of the circuit (no `s <= n`, no limb range checks, no carry range checks, no final
  assert) each accept the matching attack input. So each check is both present and necessary.
* These are tests, not a proof of soundness, and the witness solver used is ZoKrates' honest one.

## Run it

Timing on your machine (Docker Desktop; Git Bash or WSL), one command from this folder:

```
bash run_bench_hostside.sh
```

It runs 1 discarded warm-up (replicate 0) and 5 replicates of the five phases, one `docker exec` per phase, like the earlier
runs. Each phase is timed from the host (columns `compile_s` ... `verify_s`, comparable with the other rows of
`per_replicate_pipeline.csv`) and again inside the container (`*_inner_s`); the difference is the cost of `docker exec`.
Outputs: `results_rsa2048_hostside.csv` and `bench_env_hostside.txt`. Do not discard or repeat replicates; keep everything.

Why two timings: in the earlier logs the verify phase of the smallest circuit (2,559 constraints) took about 0.33 s and of
the Merkle d=8 circuit 0.84-0.97 s, while ZoKrates verifies this 153,484-constraint circuit in about 0.01 s on the cloud VM
used here. So the earlier short-phase times probably consist mostly of `docker exec` start-up; the inner columns measure it.

Other scripts and tests:

```
bash run_bench_docker.sh    # everything inside one container, inner times only (use WSL or Linux; mounts the folder)
./bench_inside.sh           # same, when zokrates 0.8.7 is on the PATH (REPS=5 WARMUP=1)

# correctness and mutation tests (needs zokrates 0.8.7, python3, the 'cryptography' package)
ZOKRATES_BIN=/path/to/zokrates ZOKRATES_STDLIB=/path/to/stdlib python3 scripts/run_tests.py all

python3 scripts/make_inputs.py "my message" valid_args.txt   # fresh key and signature
python3 scripts/build_circuit.py                             # regenerate the circuit from the template
```

`run_bench_hostside.sh` was tested here against a fake `docker` command (logic, timing and CSV only); it has not been run
with real Docker. The inner/outer difference is about 0.01 s in that test, so any larger gap on your machine is real Docker cost.

## Notes and limits

1. ZoKrates 0.8.7 deletes an `unpack` whose output bits are never used, together with its constraints (a public input
   compiles to 0 constraints; a private input fails with "unconstrained variable"). Each range check therefore asserts that
   the recomposed bits equal the value, which costs 1 extra constraint per check (1,142 checks, about 0.7% of the total).
2. The message digest is a public input. Hashing the message is not included (27,470 constraints per SHA-256 block, Table 1).
3. Only e = 65537. The modulus is a public input; a fixed-key variant would save the `q*n` products (289 per multiplication,
   4,913 in total) and was not built.
4. A straightforward implementation, not an optimised one. Known savings not taken: symmetric squaring products (136 per
   squaring, 2,176 in total) and tighter carry bounds. Other limb sizes were not compiled. Read 153,484 as the cost of a
   plain ZoKrates implementation, not a minimum.
5. Relation to the surrogate: each native multiplication in the surrogate's ladder corresponds to one modular multiplication
   here (8,889 constraints against 1), so for long exponents the surrogate's "lower bound" is loose by roughly three to four
   orders of magnitude. This is derived from the per-multiplication cost, not measured. The two circuits also model
   different operations (verification with a 17-multiplication exponent versus ladders over a long exponent).
6. Timings from this sandbox (setup 9 s, prove 4 s) are not comparable with your machine. The witness here is mostly
   0/1 bits, which provers handle cheaply, so expect a low cost per constraint; whether that is the cause is untested.
