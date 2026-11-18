# Circom/snarkjs phase analysis (18 Nov 2026)

Inputs: ../results/laptop_i7-8665U_20261118 (laptop, i7-8665U, 8 threads, node v24.16.0) and
../results/desktop_i7-10700_20261118 (desktop, i7-10700, 16 threads, node v26.13.1).
circom 2.2.3, snarkjs 0.7.6, ptau ppot_0080_20.ptau (PSE Perpetual Powers of Tau, 1,208,052,882 bytes).
Medians of passes 1-5 (pass 0 = warm-up). All proofs verified.

- circom_phases.csv: prove time split from `snarkjs groth16 prove -v` timestamps (seconds):
  startup (node start to "Reading Wtns"), read (witness + zkey coefficient section),
  qap (Building ABC: matrix evaluation), fft (IFFT/FFT), gap, msm (A, B1, B2, C, H), tail.
- circom_msm_split.csv: each multiexp separately; wire_msm = A+B1+B2+C (H runs over the quotient polynomial).
- Re-run from this folder: python3 phases.py ../results ; python3 msm.py ../results (writes the two CSV files here).
