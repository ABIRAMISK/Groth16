#!/bin/bash
# One-minute check before a session (Git Bash): machine, power, Docker, image, Python with the 'cryptography' package, disk space.
# Run it on every machine you use. It writes .machine (a short CPU label used in the name of the results zip) and .pybin.
export MSYS_NO_PATHCONV=1      # without this Git Bash turns  cmd.exe /c  into a path and Windows waits for typing
cd "$(dirname "$0")" || exit 1
source ./envlib.sh
ok=1
echo "== machine"
TAG=${MACHINE:-$(machine_tag)}; echo "$TAG" > .machine
echo "cpu:    $(cpu_name)  ($(cores))"
echo "system: $(sys_model)"
echo "os:     $(os_info)"
echo "label:  $TAG   (goes into the name of the results zip; to choose another:  MACHINE=name bash check_setup.sh)"
echo "== power"
b=$(ac_state)
if [ -z "$b" ]; then echo "no battery reported: this is a desktop PC (fine)"; else echo "battery status (2 = plugged in, 1 = on battery): $b"; fi
[ "$b" = 1 ] && { echo "!!! The laptop is on BATTERY. Plug in the charger and run this again."; ok=0; }
echo "active power plan: $(powercfg.exe /getactivescheme 2>/dev/null < /dev/null | tr -d '\r' | sed 's/^Power Scheme GUID: *//')"
echo "Power mode setting when plugged in (overlay GUID): $(pm_ac)    (Best performance = ded574b5-45a0-4f42-8737-46345c09c238)"
if [ "$(pm_ac)" != "ded574b5-45a0-4f42-8737-46345c09c238" ]; then
  if [ -z "$b" ]; then echo "note (desktop): the active power plan above should be High performance, or Balanced with no power saving."
  else echo "!!! Power mode is not 'Best performance': Settings > System > Power & battery > Power mode (when plugged in)."; fi
fi
power_summary
if [ "$SLEEP_BAD" = 1 ]; then
  echo "!!! The screen timer, sleep or closing the lid can still put this computer into standby. Modern Standby / sleep can break Docker's disk (Input/output error) and stop the run. Run  bash prep_power.sh  once, then this check again. (To start anyway:  FORCE=1 bash run_all.sh)"
  [ -z "${FORCE:-}" ] && ok=0
fi
echo "== docker"
if docker info > /dev/null 2>&1; then
  echo "Docker is running: $(docker_cpus) CPUs and $(docker_mem_gib) GiB memory available to containers"
  awk -v m="$(docker_mem_gib)" 'BEGIN{exit !(m+0>0 && m+0<6)}' && echo "!!! Docker has less than 6 GiB. The ECDSA and RSA-4096 circuits need up to about 4.5 GiB while compiling and may be killed (README section 5 says how to give Docker more)."
else echo "!!! Docker is NOT running: start Docker Desktop and wait until it says it is running."; ok=0; fi
if docker image inspect zokrates/zokrates:0.8.7 > /dev/null 2>&1; then echo "image zokrates/zokrates:0.8.7 is present"; else echo "image zokrates/zokrates:0.8.7 is not present yet; the first run pulls it (needs internet)"; fi
echo "== python (needed only for the native baseline, step 1)"
rm -f .pybin
for c in "python" "python3" "py -3"; do
  if $c -c "import cryptography,sys; print('ok', sys.version.split()[0], 'cryptography', cryptography.__version__)" 2>/dev/null; then echo "$c" > .pybin; break; fi
done
[ -f .pybin ] || echo "NOTE: no Python with the cryptography package. Step 1 (native baseline, 2 minutes) will be skipped. To enable it:  python -m pip install cryptography   (or  py -3 -m pip install cryptography)  and run this check again."
echo "== disk"
echo "drives (Git Bash view):"; df -h 2>/dev/null | awk 'NR==1 || $NF == "/" || $NF ~ /^\/[a-z]$/'      # Git Bash lists C: as "/" (the Git folder) and the other drives as /d, /e
DP=$(disk_path); DD=$(docker_data_dir); DL=$(echo "$DP" | tr -d / | tr a-z A-Z)
if [ -n "${DISKPATH:-}" ]; then echo "Docker's virtual disk is assumed to be on drive $DL: (you set DISKPATH=$DISKPATH)"
elif [ -n "$DD" ]; then echo "Docker's virtual disk is in a custom folder: $DD   (drive $DL:)"
else echo "Docker's virtual disk is in its default place, on C: (to move it to another drive: README section 5)"; fi
fg=$(host_free_gb)
if [ -n "$fg" ]; then
  echo "free space on $DL: ${fg} GB (Docker's virtual disk lives there and grows during the run)"
  if awk -v f="$fg" 'BEGIN{exit !(f+0<10)}'; then
    echo "!!! Less than 10 GB free on $DL:. A full drive crashed Docker in the first session (Input/output error). Free at least 15 GB (Recycle Bin, Downloads, Disk Cleanup) or move Docker's disk to another drive (README section 5), then run this again. To start anyway:  FORCE=1 bash run_all.sh"
    [ -z "${FORCE:-}" ] && ok=0
  elif awk -v f="$fg" 'BEGIN{exit !(f+0<15)}'; then echo "note: under 15 GB free on $DL:. Enough for the run, but free more if you can."; fi
fi
if [ "$DP" != /c ]; then
  cg=$(free_gb_of /c)
  if [ -n "$cg" ]; then
    echo "free space on C: ${cg} GB (Windows itself needs some room)"
    if awk -v f="$cg" 'BEGIN{exit !(f+0<3)}'; then echo "!!! Less than 3 GB free on C:. Windows and Docker Desktop need room for logs and settings. Free some space and run this again. To start anyway:  FORCE=1 bash run_all.sh"; [ -z "${FORCE:-}" ] && ok=0; fi
  fi
fi
echo "== reminders: close all other programs and browser tabs, screen and sleep = Never while plugged in, pause Windows Update."
[ "$ok" = 1 ] && echo "READY" || { echo "NOT READY: fix the lines marked !!!"; exit 1; }
