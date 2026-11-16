# Running the measurement on Linux (GitHub Codespaces, Google Colab, any Linux machine)

Same circuits, same phases, same timers, same CSV format as the Windows sessions. Two ways to execute ZoKrates 0.8.7:

* **docker** (used automatically when Docker works, e.g. Codespaces): the official image `zokrates/zokrates:0.8.7`, one `docker exec` per phase, as on the two Windows machines. A bind-mount control (two circuits) is added at the end.
* **native** (used automatically when there is no Docker, e.g. Colab): the ZoKrates 0.8.7 release binary, downloaded by `check_setup_linux.sh`, run directly on the local disk of the machine (no container).

The result folders have the same layout as the Windows ones; `env.txt` records mode, CPU, kernel, hypervisor, memory, cgroup limits and the sha256 of the ZoKrates binary, and `pass_log.txt` records load average and CPU steal time at the start and end of every pass (the part of a cloud machine's noise that can be measured).

## Codespaces (Docker mode)

1. GitHub > your profile picture > Settings > Codespaces > **Default idle timeout** = 240 minutes (the maximum).
2. Open a repository of yours > green **Code** button > **Codespaces** tab > **...** > **New with options** > Machine type **4-core** (16 GB) > Create. (2-core has 8 GB: too tight for ECDSA and RSA-4096.)
3. When the editor has opened, drag **zkp_v4d.zip** from your computer into the Explorer panel on the left.
4. Open the terminal (Ctrl+`) and type, one at a time:
   * `unzip -q zkp_v4d.zip && cd zkp_v4`
   * `bash start_linux.sh quick` then, after about three minutes, `bash status_linux.sh` (it must say "not running", and the last lines of the log must end with "All steps finished" with no line starting with `!!!`)
   * `bash start_linux.sh` (the full session, about 3 to 4 hours on 4 cores; it runs in the background)
5. Look at it from time to time with `bash status_linux.sh`. Keep the browser tab open. If the Codespace stopped, open it again and run `bash start_linux.sh`: it continues where it stopped.
6. At the end the status says "not running" and the file `zkp_v4_results_codespaces-4c.zip` exists: right-click it in the Explorer > Download.

A 4-core Codespace uses 4 of your 120 free core-hours per hour, so one full session costs about 12 to 16 core-hours.

## Google Colab (native mode)

1. colab.research.google.com > File > Upload notebook > **zkp_colab.ipynb**. Runtime > Change runtime type > **CPU** (no GPU).
2. Run the cells from the top, one at a time (Shift+Enter). Cell 1 asks for **zkp_v4d.zip**. Cell 2 connects Google Drive (results are copied there after every pass, so a dropped session loses at most one pass). Cell 3 is a 2-minute check. Cell 4 starts the full session. Cell 5 shows progress every 5 minutes: **leave the tab open**.
3. If Colab disconnects: open the notebook again, run cells 1, 2 and 4: the unfinished session continues from the copy on Drive.
4. Cell 6 packs the results and downloads `zkp_v4_results_colab-2c.zip`.

Free Colab has about 2 CPUs and 12 GB of memory, is shared, and may give a different CPU model each time; expect about 3 to 4 hours.

## Optional: GitHub Actions

`.github/workflows/zkp-linux.yml` runs the same session on a GitHub-hosted runner when the package is the root of the repository (Actions tab > ZKP Linux session > Run workflow). Not tested by the authors.

## Notes for the paper

* Cloud machines are shared; the timings of such a session are reported as a separate environment, never mixed with the other machines. If the steal time or the load average in `pass_log.txt` is not close to zero, say so.
* Do not use the machine for anything else while the session runs.
* `bash run_all_linux.sh quick` is a functional check only; its folders end in `_quick` and are not packed.
