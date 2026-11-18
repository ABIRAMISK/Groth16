# Circom 2 + snarkjs Groth16 kit

Repeats the ZoKrates measurement on an independent toolchain: Circom 2 (compiler) and snarkjs (Groth16 prover, BN254).
Same method: one warm-up and five measured passes, random order; every proof is verified.

Circuits: Poseidon chains of 64, 256 and 1024 hashes (circomlib Poseidon); SHA-256 of 256 bits (circomlib);
a square chain of 100,000 and 300,000 constraints proved twice with the same keys, once with a full-width witness
(x = 3) and once with a witness of ones (x = 1): the matched pair, with an identical constraint system.

## Needs (once per machine)
Node.js, Rust, Circom 2.2.3, snarkjs 0.7.6 (`npm install -g snarkjs@0.7.6`), circomlib in `~/zk-example`
(`npm install circomlib`), and the 2^20 Perpetual Powers of Tau file `ppot_0080_20.ptau` in `~/zk-example`, from https://pse-trusted-setup-ppot.s3.eu-central-1.amazonaws.com/pot28_0080/ppot_0080_20.ptau (1,208,052,882 bytes; the Hermez file linked in the snarkjs README was not downloadable on 18 Nov 2026).

## Run (Git Bash, charger plugged in, other programs closed)
    cd ~/zkp_circom
    bash run_circom.sh quick      # about 3 minutes
    bash run_circom.sh            # full run; the first time it also compiles and sets up (setup of the 300k circuit takes several minutes)

If circomlib or the .ptau file are elsewhere: `NM=/path/to/node_modules PTAU=/path/to/file.ptau bash run_circom.sh`.
Send the folder `circom_results_<date>` from each machine.
