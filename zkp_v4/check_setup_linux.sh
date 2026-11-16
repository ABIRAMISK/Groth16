#!/bin/bash
# One-minute check on a Linux machine (GitHub Codespaces, Google Colab, any Linux box): chooses the mode and fetches what is missing.
#   docker mode (used when Docker works): the official image zokrates/zokrates:0.8.7, as on the two Windows machines
#   native mode (no Docker, e.g. Colab):  the ZoKrates 0.8.7 release binary, run directly
# ZK_MODE=docker|native overrides the choice; MACHINE=name sets the label in the name of the results zip.
cd "$(dirname "$0")" || exit 1
source ./envlib_linux.sh
ok=1
echo "== machine"
TAG=${MACHINE:-$(machine_tag)}; echo "$TAG" > .machine
echo "cpu:    $(cpu_name)  ($(cores))"
echo "system: $(sys_model)"
echo "os:     $(os_info)"
echo "label:  $TAG   (goes into the name of the results zip; to choose another:  MACHINE=name bash check_setup_linux.sh)"
ncpu=$(nproc); mem=$(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo)
echo "usable CPUs: $ncpu    memory: $mem GiB"
[ "$(uname -m)" = x86_64 ] || { echo "!!! This machine is $(uname -m); the ZoKrates 0.8.7 binary and image used here are x86_64."; ok=0; }
if awk -v m="$mem" 'BEGIN{exit !(m+0<6)}'; then echo "!!! Less than 6 GiB of memory: the ECDSA and RSA-4096 circuits need up to about 4.5 GiB while compiling and will probably be killed."; ok=0
elif awk -v m="$mem" 'BEGIN{exit !(m+0<9)}'; then echo "note: about 8 GiB is enough for the circuits, but with Docker running the margin is small; 16 GiB is comfortable."; fi
if [ -z "${ZK_MODE:-}" ]; then if docker info > /dev/null 2>&1; then ZK_MODE=docker; else ZK_MODE=native; fi; fi
export ZK_MODE; echo "$ZK_MODE" > .zkmode
echo "== mode: $ZK_MODE   (docker = official image, as on the Windows machines; native = release binary run directly)"
if [ "$ZK_MODE" = docker ]; then
  if docker info > /dev/null 2>&1; then echo "Docker is running: $(docker_cpus) CPUs and $(docker_mem_gib) GiB available to containers"; else echo "!!! Docker is not running (use ZK_MODE=native to run without it)"; ok=0; fi
  if docker image inspect zokrates/zokrates:0.8.7 > /dev/null 2>&1; then echo "image zokrates/zokrates:0.8.7 is present"
  else echo "pulling zokrates/zokrates:0.8.7 ..."; docker pull zokrates/zokrates:0.8.7 > /dev/null 2>&1 && echo "pulled" || { echo "!!! could not pull the image"; ok=0; }; fi
else
  mkdir -p zokrates_bin
  if ! ./zokrates_bin/zokrates --version 2>/dev/null | grep -q 'ZoKrates 0.8.7'; then
    echo "downloading the ZoKrates 0.8.7 release binary ..."
    curl -fsSL -o zokrates_bin/zok.tgz https://github.com/Zokrates/ZoKrates/releases/download/0.8.7/zokrates-0.8.7-x86_64-unknown-linux-gnu.tar.gz \
      && tar xzf zokrates_bin/zok.tgz -C zokrates_bin && rm -f zokrates_bin/zok.tgz
    chmod +x zokrates_bin/zokrates 2>/dev/null
  fi
  if ./zokrates_bin/zokrates --version 2>/dev/null | grep -q 'ZoKrates 0.8.7' && [ -d zokrates_bin/stdlib ]; then echo "$(./zokrates_bin/zokrates --version)   sha256 $(zok_sha256 ./zokrates_bin/zokrates)"
  else echo "!!! no working ZoKrates 0.8.7 binary with its stdlib in ./zokrates_bin (download failed?)"; ok=0; fi
fi
echo "== python (native baseline, step 1)"
python3 -c "import cryptography" 2> /dev/null || python3 -m pip install -q cryptography > /dev/null 2>&1 || python3 -m pip install -q --break-system-packages cryptography > /dev/null 2>&1
python3 -c "import cryptography,sys; print('ok', sys.version.split()[0], 'cryptography', cryptography.__version__)" 2> /dev/null || echo "NOTE: no Python 'cryptography' package: step 1 (native baseline, 2 minutes) will fail or be skipped"
echo "== disk"
fg=$(host_free_gb); echo "free space on $(disk_path): ${fg} GB"
if [ -n "$fg" ] && awk -v f="$fg" 'BEGIN{exit !(f+0<10)}'; then echo "!!! Less than 10 GB free where the working files go. The largest circuits need about 2 GB each at a time."; ok=0; fi
[ "$ZK_MODE" = native ] && echo "working files go to ${NATIVE_HOME:-/tmp/zk_native} (local disk)"
echo "== reminders: keep this browser tab open (Colab/Codespaces), do not start other heavy work on the machine while the session runs."
[ "$ok" = 1 ] && echo "READY ($ZK_MODE mode, $ncpu CPUs)" || { echo "NOT READY: fix the lines marked !!!"; exit 1; }
