# Cached-matrix prover kit (ZoKrates 0.8.7, ark back end)

`zokrates_fast` is ZoKrates 0.8.7 with the timers of the phase kit and one change to proving:

* At `setup`, when `ZOK_MATRIX_CACHE` names a file, ZoKrates also writes the finalized constraint matrices of the
  circuit to that file (compact form: a table of distinct coefficients, then each matrix row by row). This is done
  once per circuit, from the compiled program alone (no witness).
* At `generate-proof`, when that file exists, ZoKrates reads it and the witness, builds the full assignment and runs
  the same Groth16 arithmetic as before (witness map, FFTs, five multi-scalar multiplications). It does not decode the
  compiled program or rebuild the constraint system.
* In addition, each linear combination is built in one go and sorted once, instead of one sorted insert per term.

Proofs are standard Groth16 proofs for the same proving and verification keys: they are checked with the unchanged
`zokrates verify`. Nothing changes when `ZOK_MATRIX_CACHE` is not set. The run scripts set it (to `matrices.bin` in
each circuit's folder) when `FAST=1` is given.

## Files (copy all into the zkp_v4 folder; the scripts replace the earlier ones, the circuits go into `circuits`)

* `zokrates_fast`, `zokrates_timers`   the cached-matrix binary and the phase-kit binary (checksums in `binaries.sha256`)
* `zok_wrap.sh`, `run_phases.sh`, `run_phases_linux.sh`, `zprep.sh`, `phases_extract.py`   updated scripts; every earlier mode still works
* `circuits/eddsa_*`   the EdDSA circuits (already present if the EdDSA kit was installed)
* `source_patches/`    the changes to ZoKrates 0.8.7 and ark-groth16 0.3.0 that make zokrates_fast; not needed to run

## Run (Git Bash, zkp_v4 folder, charger in, Docker Desktop running)

    FAST=1 bash run_phases.sh quick     # about 2 minutes: check
    FAST=1 bash run_phases.sh           # all 21 circuits, cached-matrix prover, about 1.5 hours on the laptop
    bash run_phases.sh                  # the same 21 circuits with the original prover, same day, about 2 hours
    FAST=1 bash run_phases.sh eddsa     # the two EdDSA circuits, about 10 minutes

Folders: `phases_fast_<date>` (cached) and `phases_<date>` (original). Send all three.
In the summary, "front-end" for the cached runs is reading the stored matrices plus building the assignment.
The setup time of the cached runs includes writing the matrices (lines `setup.prep_synthesis` and `setup.prep_write` in raw_run.log).
