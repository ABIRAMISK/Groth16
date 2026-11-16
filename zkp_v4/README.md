# zkp_v4: the whole measurement for the paper, in one sitting, on two machines

**Linux (GitHub Codespaces, Google Colab, any Linux machine): see `LINUX.md`.** The Windows instructions below are unchanged; the Linux scripts are `*_linux.sh` and are derived from the Windows ones by `make_linux_scripts.py` (the measurement logic is the same).

ZoKrates 0.8.7, Groth16, BN254, official image `zokrates/zokrates:0.8.7`. Same method as the session of 11 Nov (container-local
storage, timers inside the container, one warm-up pass and five measured passes in a random order, nothing discarded). New:

* **Real RSA verifiers at four key sizes** (PKCS#1 v1.5, SHA-256, e = 65537): 1024 bits = 76,604 constraints, 2048 = 153,484
  (unchanged), 3072 = 244,870, 4096 = 331,848. Each was tested with the real ZoKrates 0.8.7 before this package was made: 12 accept/reject cases per size
  (flipped digest bit, s+1, wrong modulus, s+n, out-of-range limbs, off-by-one quotient, two forgeries), 20 (1024 bits) or 4 (3072, 4096)
  fresh random keys accepted, and four weakened copies of the 1024-bit circuit that each accept the attack their missing check should stop.
  Reports: `generators\rsa\test_report_*.txt`.
* **Four synthetic circuits for the mechanism experiment.** A chain x = x*x + 1 whose witness values are all full-width field elements, and a chain
  of XOR/OR steps on bits whose witness values are all 0 or 1. Each exists at two sizes, and the two chains are matched in constraints
  (100,001 against 100,002 and 300,001 against 300,002). They show how much of the prover time depends on the values in the witness and not on the
  constraint count. The witness and R1CS statistics of every circuit are computed afterwards from the same files (see `analysis/` in the repository), so nothing extra has to be run for them.
* **SHA-256 baseline circuit** (the repository's `hash_circuit.zok`; compiles to **27,214** constraints, not 27,470) with an ECC-derived and an RSA-derived input,
  timed like every other circuit.
* **Native baseline on each machine** (step 1): RSA 1024/2048/3072/4096 sign and verify, ECDSA SECP256K1 and SECP256R1 sign and verify,
  1,000 iterations each. Replaces the old classical tables.
* **Memory profile** (step 3): peak memory and CPU time of the ZoKrates process per phase for every circuit, from `/proc` (one untimed visit each).
* **Two machines.** The same package and the same single command run once on each machine (section 6). Each machine makes its own zip.

## 1. Folders

Extract `zkp_v4c.zip` so that the folder is **`C:\zkp_v4`** (right-click the zip > Extract All > in the box type `C:\` > Extract). A short path on the C: drive,
not inside Downloads, OneDrive or the Desktop, on every machine. Any other place works too if you `cd` into it.

```
C:\zkp_v4\
  README.md  run_all.sh  check_setup.sh  prep_power.sh  pack_results.sh
  classical_bench.py           step 1, native baseline, about 2 minutes
  run_remeasure.sh             step 2, ZKP session, 28 circuits, about 2 hours
  run_memory_profile.sh        step 3, memory profile, about 20 minutes
  zphase.sh  zprep.sh  zprofile.sh  envlib.sh      helpers (zphase/zprep/zprofile run inside the container)
  circuits\                    every circuit and its fixed input (rsa1024/2048/3072/4096, ecdsa, sha256, synthetic chains, poseidon, merkle, rsa accumulator)
  generators\                  Python that made the new circuits, with test reports (not needed to run; for GitHub)
  native_<date>_<time>\        created by step 1
  results_<date>_<time>\       created by step 2
  memory_<date>_<time>\        created by step 3
  zkp_v4_results_<cpu>.zip     created at the end (pack_results.sh)
```

## 2. Before you start (on every machine)

* **Laptop: plug in the charger.** Settings > System > Power & battery > Power mode (plugged in) = **Best performance**; screen and sleep = **Never** while
  plugged in. The scripts stop with a message if Windows reports battery. **Desktop:** no battery is fine; the active power plan should be High performance
  (or Balanced), sleep = Never.
* **Screen, sleep and lid.** Run `bash prep_power.sh` once on each machine: it keeps the screen on and turns off sleep, hibernate and lid-close sleep while plugged in (the check at the start refuses to run otherwise).
  On a Modern Standby laptop the 5-minute screen-off timer alone puts the computer into standby, and Modern Standby / sleep can break Docker's disk (`Input/output error`) and stop the run. Never close the lid during a run.
* Close every other program and all browser tabs. Docker Desktop must be running (WSL 2 engine). Pause Windows Update for a week. Leave the computer alone while it runs.
* Python with the `cryptography` package is needed for step 1 only: in Git Bash `python -m pip install cryptography` (or `py -3 -m pip install cryptography`).
  Without it, step 1 is skipped and everything else runs.
* Free disk space: **at least 15 GB free on the drive that holds Docker's virtual disk** (C: unless you moved it; see section 5) **and at least 3 GB on C:** for Windows itself. Docker needs at least 6 GiB of memory for the largest circuits (the check at the start prints all of this).

## 3. The command (Git Bash)

Open Git Bash, then type these three lines **one at a time** and press Enter after each. Do not paste several commands at once and do not type anything while it runs:

```bash
cd /c/zkp_v4
bash prep_power.sh        # once per machine: screen stays on, no sleep, no lid-close sleep while plugged in
bash run_all.sh
```

`prep_power.sh` prints the new settings and ends with `OK`. `run_all.sh` checks the machine (a minute; stops with a message marked `!!!` if something is wrong, fix that and start again), then runs step 1 (about 2 minutes), step 2
(about 2 hours; starts after a 15 s countdown) and step 3 (about 20 minutes), then packs the results into `zkp_v4_results_<cpu label>.zip` (for example
`zkp_v4_results_i7-8665U.zip`) in the same folder. The whole run takes about 2.5 hours.

Only the check, without starting anything (about one minute): `bash check_setup.sh`.

If a step stops (sleep, Docker restart, a crash), run **the same command again with the folder name it printed**, on the same machine, and then pack:

```bash
RESUME=results_20261113_090000 bash run_remeasure.sh
RESUME=memory_20261113_120000 bash run_memory_profile.sh
python classical_bench.py --resume native_20261113_085500
bash pack_results.sh
```

Single steps: `python classical_bench.py` (step 1; if "python" is not found: `py -3 classical_bench.py`), `bash run_remeasure.sh` (step 2), `bash run_memory_profile.sh` (step 3),
`bash run_remeasure.sh quick` (3-minute check of the harness), `bash run_remeasure.sh rsareal` (only the four real RSA verifiers, about 25 minutes),
`bash run_remeasure.sh synth` (only the four synthetic circuits, about 25 minutes), `python classical_bench.py --suite full` (the old classical tables, about 45-60 minutes).

## 4. When it prints "All steps finished": collect the zip

Keep `zkp_v4_results_<cpu label>.zip` (one per machine). If any line shows `status=` other than `OK`, or the screen shows `Killed`, keep the last 40 lines of the output with it.
To pack again by hand: `bash pack_results.sh`.

## 5. Memory and disk

* **Disk.** Docker keeps all images and containers in one big file (`docker_data.vhdx`) that grows while the circuits run. By default it is on C:; if you moved it (below), it is in the folder you chose. A full drive makes Docker fail with `Input/output error` in the middle of a circuit (the first session ended that way after 67 minutes with C: at 62 MB free; the screen turning off and Windows going to standby can break it too, see section 2). Keep **at least 15 GB free on the drive that holds that file and at least 3 GB on C:**. The check at the start prints both and refuses to start below 10 GB (Docker's drive) or 3 GB (C:); during the run it stops by itself, before a measurement is damaged, if Docker's drive falls below 3 GB or C: below 1 GB. If a run stops with the message that the
  container stopped or its disk failed, the visit it was in is **not** marked done: free space, restart Docker Desktop (whale icon > Quit, start it again), and give the
  same `RESUME=... bash run_remeasure.sh` command it prints; the visit is repeated, then the run goes on. Afterwards run `bash run_memory_profile.sh` and `bash pack_results.sh`.
* **Making room on C: without deleting your own files.** (1) Administrator terminal: `powercfg /h off` removes `hiberfil.sys` (6-12 GB on a 16 GB laptop; hibernation is off in `prep_power.sh` anyway). (2) Disk Cleanup > Clean up system files: Windows Update Cleanup, Delivery Optimization files, Temporary files, Previous Windows installation(s). (3) Settings > System > Storage shows what takes the space.
* **Moving Docker's disk to another drive** (internal drive only: not USB, not a network drive; at least 40 GB free): Docker Desktop > Settings (gear) > Resources > Advanced > Disk image location > Browse > a new empty folder such as `E:\Docker` > Apply. It takes 5-15 minutes; do not touch anything else meanwhile. If it ends with "Failed to apply settings", Docker has rolled back: use Troubleshoot (bug icon) > Reset to factory defaults (this deletes every Docker image and container, which is harmless here because the results are in the zkp folder and the image downloads again), then set the location again. The scripts find the new place from Docker's settings (`DataFolder`) and check the free space there; if that ever fails, name the drive yourself, for example `DISKPATH=/e bash run_all.sh`. `env.txt` records the drives and the type of every disk (SSD/HDD, NVMe/SATA/USB), which the paper's environment table uses.
* **Memory.** The largest circuits need the most memory when compiling: ECDSA about 4.3 GB (measured on 11 Nov), RSA-4096 probably 3-4 GB. Docker Desktop on
  the first laptop has 7.7 GB and the ECDSA circuit ran there without a problem, so nothing needs changing there. If the check warns about less than 6 GiB, or a compile
  ever ends with `Killed` or exit code 137, give the WSL engine more memory: `notepad ~/.wslconfig`, add `[wsl2]` and `memory=10GB`
  (not more than about 70 % of the RAM), then `wsl --shutdown` and restart Docker Desktop.

## 6. The second machine

It answers one question: do the cost ratios and the cost model found on the first laptop hold on a different CPU? Any Windows 10/11 PC (laptop or desktop) with
Docker Desktop (WSL 2 engine) and Git Bash will do; the more it differs from the first (other CPU generation, other core count), the more it tells. 16 GB RAM is comfortable; 8 GB works only if Docker can have 6 GiB.

1. Copy `zkp_v4c.zip` to it and extract it to `C:\` as in section 1, so the folder is `C:\zkp_v4`.
2. Same preparation as in section 2.
3. In Git Bash, one line at a time: `cd /c/zkp_v4`, then `bash prep_power.sh`, then `bash run_all.sh` (about 2.5 hours; a faster CPU needs less). The machine description (CPU, RAM, Docker allocation) is saved in the zip.
4. The two machines can run at the same time; they do not disturb each other. Do not copy result folders from one machine to the other: each session is analysed on its own and then compared.
5. If the second machine is much slower and the session would take 4 hours or more, start it as `REPS=3 bash run_all.sh` (3 replicates instead of 5) and note that with the results.

## 7. What the paper will use from this

Everything in the new version is computed from these result folders; nothing is typed by hand. The 11 Nov session stays as the earlier repeatability
check. The synthetic RSA-accumulator circuits (the older stand-in) are still in the session as a control; whether they stay in the paper is decided after the real RSA fit is seen.
