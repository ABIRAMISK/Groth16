# Groth16 proving cost: artifact

Circuits, generators, test programs, the measurement harness, the structure extractor, the statistics scripts and the replicate-level results of a measurement study of Groth16 proving cost in ZoKrates 0.8.7 (`ark-groth16` 0.3.0 backend, curve BN254).

28 circuit configurations of eight families (Poseidon chain, Merkle path, RSA-style exponentiation ladder, real RSA verifier at four key sizes, ECDSA verifier, SHA-256 compression, synthetic full-width chain, synthetic boolean chain) were measured in three sessions on three machines. Each session is analysed on its own and the sessions are compared; their timings are never pooled.

## Contents

| Path | What it holds |
|---|---|
| `zkp_v4/` | The measurement harness (bash) and every circuit. `circuits/` has the ZoKrates sources and the fixed inputs. `generators/` has the Python and the sources behind the RSA, SHA-256 and synthetic circuits, with the RSA test reports. `README.md` (Windows: Git Bash and Docker Desktop) and `LINUX.md` (Linux, Codespaces, Colab) describe how to run it. |
| `colab/zkp_colab.ipynb` | Notebook of the Colab session (native ZoKrates binary, no container). |
| `generators/ecdsa/` | Pure-Python generator of the ECDSA (secp256k1) verifier circuit and its fixed input, with test programs and their results. |
| `analysis/` | Structure extractor (`r1cs_features3.py`, driver `struct_driver.sh`); statistics (`stats_v4.py`, `fit_model.py`, `stats_v3.py`, driver `run_stats.sh`); figures (`make_figs_v8.py`); the 28 configurations (`configs.tsv`: id, family, parameter, type, constraint count, p1, p2); shipped outputs `features3.jsonl` and `stats6.json`. |
| `data/` | Raw results, listed below. `data/build/stats.json` is the shipped output of `stats_v3.py`. |

## Sessions in `data/`

Every session has one warm-up pass (replicate 0, excluded from every statistic) and five measured passes (replicates 1 to 5); the visit order is random in every pass.

| Folder | Session | Machine | Role |
|---|---|---|---|
| `res_lap/` | 13 Nov 2026, 28 circuits | Laptop: Dell Latitude 7400, Intel Core i7-8665U (4 cores, 8 threads), 15.8 GiB, Windows 11 Pro, Docker Desktop (WSL 2) with 8 CPUs | main session |
| `res_desk/` | 13 Nov 2026, 28 circuits | Desktop: Intel Core i7-10700 (8 cores, 16 threads), 15.9 GiB, Windows 10 Pro, Docker Desktop (WSL 2) with 16 CPUs | main session |
| `res_colab/` | 13 Nov 2026, 28 circuits | Google Colab virtual machine: Intel Xeon @ 2.20 GHz (1 core, 2 threads), 12.7 GiB, Ubuntu 24.04, KVM; ZoKrates binary run directly, no container | replication on Linux |
| `res_full/` | 11 Nov 2026, 19 circuits | the laptop above | earlier session (agreement check) |
| `zips/res9nov/` | 9 Nov 2026, 18 circuits | the laptop above | earlier session (agreement check) |
| `zips/ecdsa_bat/`, `zips/ecdsa_ac/`, `zips/ecdsa_perf/` | 11 Nov 2026, ECDSA verifier alone | the laptop above: on battery with "Best power efficiency"; on mains with that mode; on mains with "Best performance" | power-state study |
| `res_part/` | 12 Nov 2026, interrupted attempt (Docker's disk filled the system partition) | the laptop above | pilot, not used in any statistic |

Other folders: `rsa_multi/tests_all_sizes.log` (accept/reject tests of the real RSA verifiers at 1024, 2048, 3072 and 4096 bits), `table_ecc/` (BabyJubJub circuits and their compile-only constraint counts), `pkg_v3/` (README of the RSA-2048 circuit of an earlier package).

Inside a session folder:

| File | Content |
|---|---|
| `results_<date>_<time>/results.csv` | One row per circuit, replicate and visit: constraints; `compile_s`, `setup_s`, `witness_s`, `proof_s`, `verify_s` measured around each phase on the host (including `docker exec` in the Docker sessions); `*_inner_s` measured inside the container around the ZoKrates command (the statistics use these); `verify_passed`, `visit_position`, `status`. |
| `results_<date>_<time>/results_bind_control.csv` | Control visits with the working folder on a Windows bind mount, where that control was run. |
| `results_<date>_<time>/order.txt`, `pass_log.txt`, `env.txt`, `raw_run.log`, `done.list`, `power_events.txt` | Visit order of every pass; start and end of every pass (power state, clock, free disk; on Linux also load and CPU steal time); machine, software versions and settings; the complete log; finished visits; Windows sleep and wake events where recorded. |
| `native_<date>_<time>/raw_classical.csv` | Native baseline: 1,000 iterations of RSA 1024/2048/3072/4096 and ECDSA SECP256K1/SECP256R1 signing and verification (`env.json`, `run_log.txt` beside it). |
| `memory_<date>_<time>/memory_profile.csv` | Peak resident memory and CPU time of the ZoKrates process per circuit and phase. |
| `machine_<label>.txt` | Description of the machine (CPU, memory, Docker allocation, disks). |

## Regenerate the statistics from the raw results (Python only)

Needs Python 3 with `numpy` and `scipy`.

```
python3 -m pip install numpy scipy
bash analysis/run_stats.sh
cmp analysis/stats6_regenerated.json analysis/stats6.json && cmp analysis/stats3_regenerated.json data/build/stats.json && echo identical
```

`stats6.json` holds the statistics of the three main sessions (with the two earlier laptop sessions for the agreement check); `data/build/stats.json` those of the earlier sessions and the power-state runs. With Python 3.13, numpy 2.5.3 and scipy 1.18.1 on Linux x86-64 both regenerated files are byte-identical to the shipped ones; other library versions can change the last digits of floating-point values.

Figures: `python3 analysis/make_figs_v8.py analysis/stats6.json figs` (needs `matplotlib`) writes the five figures as PDF and PNG and `m_density_values.json`.

## Regenerate the structure features (needs ZoKrates 0.8.7)

`analysis/struct_driver.sh` prepares, compiles and runs every circuit of `analysis/configs.tsv` with ZoKrates 0.8.7 and extracts the structure of the R1CS and of the witness (non-zeros of A, B and C, bit lengths of the witness values, multi-exponentiation sizes and the operation counts of the `ark-ec` 0.3.0 window model).

```
ZOKRATES=/path/to/zokrates ZOKRATES_STDLIB=/path/to/stdlib bash analysis/struct_driver.sh            # all 28
ZOKRATES=/path/to/zokrates ZOKRATES_STDLIB=/path/to/stdlib bash analysis/struct_driver.sh merkle_8    # one or more ids
```

The binary and the `stdlib` folder come from the same release archive, the one the harness downloads: <https://github.com/Zokrates/ZoKrates/releases/download/0.8.7/zokrates-0.8.7-x86_64-unknown-linux-gnu.tar.gz>. The output is `analysis/work/features3.jsonl`. Every field except `secs` (wall-clock seconds) is deterministic and equals the shipped `analysis/features3.jsonl`. The shipped run took about 17 minutes in total; the largest circuits need several GB of scratch space (`ZHOME`, default `/tmp/zkp_struct`).

## Re-run the measurements

* **Windows** (Windows 10/11, Docker Desktop with the WSL 2 engine, Git Bash): follow `zkp_v4/README.md`; `bash prep_power.sh`, then `bash run_all.sh`, about 2.5 hours.
* **Linux, Codespaces, Colab**: follow `zkp_v4/LINUX.md` and `colab/zkp_colab.ipynb`; about 3 to 4 hours on 2 to 4 cores.

Both ask for the package as `zkp_v4d.zip`. Make it from this repository (the archive must contain the folder `zkp_v4` at its top level):

```
zip -r zkp_v4d.zip zkp_v4
```

The GitHub Actions workflow mentioned at the end of `LINUX.md` is not part of this repository.

## Regenerate the circuits (Python only)

| Circuit | Command | Output |
|---|---|---|
| RSA verifier, 1024, 2048, 3072 or 4096 bits | `RSA_BITS=1024 python3 zkp_v4/generators/rsa/scripts/build_circuit.py` | `rsa<bits>_verify.zok` in `zkp_v4/generators/rsa/` (identical to `zkp_v4/circuits/rsa<bits>_verify.zok`) |
| ECDSA verifier | `python3 generators/ecdsa/build_circuit.py OUT_DIR` | `ecdsa_verify.zok`, `ecdsa_args.txt`, `ecdsa_input.json` (identical to the shipped files) |
| Four synthetic chains | `python3 zkp_v4/generators/synth/make_synth.py` | `synth_*.zok` and `synth_*_args.txt` in `zkp_v4/circuits/` (identical to the shipped files) |

`zkp_v4/generators/sha256/make_sha_args.py OUTDIR` (needs the `cryptography` package) makes the two witness files of the SHA-256 baseline circuit from freshly generated random keys, so its values differ from the shipped `sha256_args_ecc.txt` and `sha256_args_rsa.txt`, which are the files every session used. The test programs of the RSA verifier (`zkp_v4/generators/rsa/scripts/run_tests.py`, `run_extra.py`) and of the ECDSA verifier (`generators/ecdsa/tests/`) call ZoKrates; their reports are `zkp_v4/generators/rsa/test_report_*.txt`, `data/rsa_multi/tests_all_sizes.log` and `generators/ecdsa/tests/results/`.

## What has been checked

* From a copy that holds only the scripts and the raw data, `analysis/run_stats.sh` reproduces `analysis/stats6.json` and `data/build/stats.json` byte for byte (versions above).
* The structure extractor, run with the ZoKrates 0.8.7 release binary on `merkle_8`, `rsa_256_1` and `merkle_16`, reproduces every deterministic field of `analysis/features3.jsonl`.
* The generators in the last table reproduce the shipped circuits (RSA at all four sizes, ECDSA, the four synthetic chains) byte for byte.

Not re-run for this repository: the other 25 configurations of the extractor, the measurement sessions themselves, and the test programs that call ZoKrates.

## Licence

Released under the MIT licence, see `LICENSE`. Three files contain code from the ZoKrates standard library (LGPL-3.0) and keep that licence; they are listed in `NOTICE.md`, and the licence texts are in `LICENSES/`.
