# Second toolchain: Circom 2.2.3 + snarkjs 0.7.6

Check of the main mechanisms of the paper (Section 5.2) in another Groth16 toolchain.

- `kit/`: circuits (Poseidon chains, SHA-256 on 256 bits, squaring chains with full-width and boolean witnesses),
  the run script and helpers; see `kit/README_CIRCOM.md`.
- `results/`: raw results of the laptop (i7-8665U) and desktop (i7-10700) runs of 18 Nov 2026
  (one warm-up and five measured passes in random order; every proof verified). Host names are replaced by `<host>`.
- `analysis/`: scripts that turn the timestamped `snarkjs groth16 prove -v` logs into phase times
  (`circom_phases.csv`) and per-MSM times (`circom_msm_split.csv`), the source of Table 9 of the paper and Tables S13-S14 of the supplement.
