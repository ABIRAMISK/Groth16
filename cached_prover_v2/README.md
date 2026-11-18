# Cached-matrix prover, version 2 (adds the program check)

Patches against ZoKrates 0.8.7 (tag `0.8.7`) and `ark-groth16` 0.3.0.

What changed from version 1 (the version used for the timings in the paper):
- `setup` and `generate-proof` compute the SHA-256 digest of the compiled program when `ZOK_MATRIX_CACHE` is set.
- The matrix file starts with the 8-byte tag `ZOKMC01\0` and that 32-byte digest.
- `generate-proof` stops with an error if the file was written for another program
  ("the matrix cache ... was not written for this compiled program; run setup again with ZOK_MATRIX_CACHE set").

Cost of the check (separate Linux machine, 2 vCPUs, 3 proofs each): 0.03 s for the RSA-1024 verifier (33 MB program),
0.29 s for the ECDSA verifier (341 MB program, about 3% of its cached proof). All proofs verified; a matrix file of
another program was refused (exit code 1).

Use:
    ZOK_MATRIX_CACHE=$PWD/matrices.bin zokrates setup
    zokrates compute-witness -a ...
    ZOK_MATRIX_CACHE=$PWD/matrices.bin zokrates generate-proof
    zokrates verify

Build: apply `zokrates-0.8.7-fast.patch` in the ZoKrates source tree, unpack `ark-groth16` 0.3.0 next to it as
`ark-groth16-fast` and apply `ark-groth16-0.3.0-fast.patch` there, then
    cargo build --release -p zokrates_cli --no-default-features --features ark,bellman
The patch also keeps the phase timers (lines starting with ZKT on standard error).
