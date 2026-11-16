#!/usr/bin/env python3
"""Derives the Linux variants of the harness from the Windows scripts that produced the paper's two sessions, with asserted, documented edits.
The measurement logic (circuit list, visit order, phases, timers, CSV format) is NOT changed; only how a command is executed (docker exec or directly)
and how the environment is captured.  usage: python3 -I make_linux_scripts.py <package folder>"""
import sys, os, re, difflib
P = sys.argv[1]
def rd(n): return open(os.path.join(P, n), encoding="utf-8", newline="").read()
def wr(n, t, mode=0o755):
    p = os.path.join(P, n); open(p, "w", encoding="utf-8", newline="\n").write(t); os.chmod(p, mode)
def sub1(t, old, new, count=1):
    assert t.count(old) == count, "expected %d match(es), found %d for: %r" % (count, t.count(old), old[:90])
    return t.replace(old, new)
def between(t, start, end, new):
    a = t.index(start); b = t.index(end, a); assert t.count(start) == 1
    return t[:a] + new + t[b:]

# ---------------------------------------------------------------------------------------------------- envlib_linux.sh
ENV = r'''# Shared helpers for the Linux variant (GitHub Codespaces, Google Colab, any Linux machine). Same function names as envlib.sh (Windows).
# Sourced by check_setup_linux.sh, run_remeasure_linux.sh, run_memory_profile_linux.sh and pack_results_linux.sh.
cpu_name(){ grep -m1 'model name' /proc/cpuinfo 2>/dev/null | sed 's/^[^:]*: *//'; }
cpu_mhz() { local m; m=$(grep -m1 'cpu MHz' /proc/cpuinfo 2>/dev/null | sed 's/^[^:]*: *//; s/\..*//'); [[ "$m" =~ ^[0-9]+$ ]] && echo "$m" || echo 0; }   # a number, 0 if the VM does not report one
os_info() { ( . /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-Linux} kernel $(uname -r)" ); }
cores()   { local t c; t=$(nproc --all 2>/dev/null || grep -c '^processor' /proc/cpuinfo); c=$(lscpu -p=CORE,SOCKET 2>/dev/null | grep -v '^#' | sort -u | wc -l); echo "${c:-?} cores, ${t} threads"; }
sys_model(){ local pn hv; pn=$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null); hv=$(lscpu 2>/dev/null | awk -F: '/Hypervisor vendor/{gsub(/^ +/,"",$2); print $2}')
             echo "${pn:-unknown model}; hypervisor ${hv:-none}; RAM $(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo) GiB"; }
ac_state(){ echo ""; }                      # cloud machines have no battery
pm_ac()   { echo "n/a"; }
pm_dc()   { echo "n/a"; }
power_events()  { :; }
power_summary() { SLEEP_BAD=0; return 0; }
docker_data_dir() { [ "${ZK_MODE:-docker}" = docker ] && docker info 2>/dev/null | sed -n 's/^ *Docker Root Dir: *//p' | head -1; return 0; }
disk_path() {                               # the folder whose file system receives the circuits' working files
  [ -n "${DISKPATH:-}" ] && { echo "$DISKPATH"; return 0; }
  if [ "${ZK_MODE:-docker}" = native ]; then mkdir -p "${NH:-/tmp/zk_native}" 2>/dev/null; echo "${NH:-/tmp/zk_native}"; return 0; fi
  local d; d=$(docker_data_dir); [ -n "$d" ] && [ -d "$d" ] && { echo "$d"; return 0; }; echo "/"
}
free_gb_of()    { df -k "$1" 2>/dev/null | awk 'NR==2{printf "%.1f", $4/1048576}'; }
host_free_gb()  { free_gb_of "$(disk_path)"; }
disk_low() {                                # returns 0 and prints the reason when the disk is nearly full
  local fg; fg=$(host_free_gb)
  if [ -n "$fg" ] && awk -v f="$fg" 'BEGIN{exit !(f+0<3)}'; then echo "only ${fg} GB free on $(disk_path)"; return 0; fi
  return 1
}
disk_info()     { df -h 2>/dev/null | head -20; lsblk -o NAME,SIZE,TYPE,ROTA,MOUNTPOINT 2>/dev/null | head -20; }
docker_cpus()    { docker info 2>/dev/null | awk '/ CPUs:/{print $2; exit}'; }
docker_mem_gib() { docker info 2>/dev/null | awk '/Total Memory/{v=$3; if (v ~ /MiB/) {sub(/MiB/,"",v); v=v/1024} else {sub(/GiB/,"",v)} printf "%.1f", v; exit}'; }
# short label used in the name of the results zip: MACHINE=... overrides; otherwise codespaces-<n>c, colab-<n>c or <cpu>-<n>c
machine_tag() {
  local n t; n=$(nproc 2>/dev/null || echo 0)
  if [ "${CODESPACES:-}" = true ]; then echo "codespaces-${n}c"; return 0; fi
  if [ -n "${COLAB_RELEASE_TAG:-}${COLAB_GPU:-}" ] || [ -d /content/sample_data ]; then echo "colab-${n}c"; return 0; fi
  t=$(cpu_name | sed -E 's/\((R|TM)\)//g; s/@.*//; s/[[:space:]]+CPU//; s/(Intel|Core|AMD|Processor|with.*)//g; s/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]+/-/g; s/[^A-Za-z0-9-]//g')
  [ -n "$t" ] || t=$(hostname | tr -cd 'A-Za-z0-9-')
  echo "${t}-${n}c"
}
zok_sha256() { local b="${1:-}"; [ -n "$b" ] && [ -f "$b" ] && sha256sum "$b" 2>/dev/null | cut -d' ' -f1; }
capture_env_basic() {
  echo "# captured $(date -u +%FT%TZ) (host clock)   mode=${ZK_MODE:-docker}"
  echo "# host"; uname -a; echo "os: $(os_info)"
  echo "cpu: $(cpu_name)  ($(cores))   clock_mhz=$(cpu_mhz)"
  echo "system: $(sys_model)"
  echo "nproc=$(nproc)  codespaces=${CODESPACES:-no}  colab=$([ -n "${COLAB_RELEASE_TAG:-}${COLAB_GPU:-}" ] && echo yes || echo no)  virt=$(systemd-detect-virt 2>/dev/null || echo unknown)"
  echo "# lscpu"; lscpu 2>/dev/null | grep -vE '^(Flags|Vulnerability)' | head -40
  echo "# memory"; grep -E 'MemTotal|MemAvailable|SwapTotal' /proc/meminfo
  echo "# cgroup limits (max = none)"; for f in /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max; do [ -r "$f" ] && echo "$f: $(cat $f)"; done
  echo "# cpu frequency policy"; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "no cpufreq information (virtual machine)"
  if [ "${ZK_MODE:-docker}" = docker ]; then
    echo "# docker"; docker --version; docker info 2>/dev/null | grep -E "CPUs|Total Memory|Operating System|Kernel Version|Server Version|Docker Root Dir|Storage Driver"
  fi
  echo "# disks"; disk_info
  echo "working disk: $(disk_path)  free_gb=$(host_free_gb)"
}
'''
wr("envlib_linux.sh", ENV, 0o644)

# ---------------------------------------------------------------------------------------------------- run_remeasure_linux.sh
t = rd("run_remeasure.sh")
t = sub1(t, "#!/bin/bash\n", "#!/bin/bash\n# LINUX VARIANT (GitHub Codespaces, Google Colab, any Linux machine), derived from run_remeasure.sh by make_linux_scripts.py; the measurement logic is unchanged.\n"
         "# ZK_MODE=docker (default when Docker works): the official image zokrates/zokrates:0.8.7, one `docker exec` per phase, as in the Windows sessions.\n"
         "# ZK_MODE=native: the ZoKrates 0.8.7 release binary run directly in a scratch folder on the local disk (for machines without Docker, e.g. Colab); no container, no docker exec.\n"
         "# Extra variables: AFTER_PASS_HOOK='shell command run after every pass (e.g. copy $RES to Google Drive)', NATIVE_HOME=/tmp/zk_native, ZOK_BIN, ZOK_STD.\n")
t = sub1(t, "source ./envlib.sh\n",
         'ZK_MODE=${ZK_MODE:-$(cat .zkmode 2>/dev/null)}; ZK_MODE=${ZK_MODE:-docker}; export ZK_MODE\n'
         'NH=${NATIVE_HOME:-/tmp/zk_native}; ZOK_BIN=${ZOK_BIN:-$PWD/zokrates_bin/zokrates}; ZOK_STD=${ZOK_STD:-$PWD/zokrates_bin/stdlib}; NOWAIT=${NOWAIT:-1}\n'
         'source ./envlib_linux.sh\n')
t = sub1(t, 'REPS=${REPS:-5}; WARMUP=${WARMUP:-1}; CONTROL=${CONTROL:-1}\n',
         'REPS=${REPS:-5}; WARMUP=${WARMUP:-1}; CONTROL=${CONTROL:-$([ "$ZK_MODE" = docker ] && echo 1 || echo 0)}\n')
t = sub1(t, "cleanup() { docker rm -f zkp_bench zkp_ctl > /dev/null 2>&1; }\n",
         'cleanup() { [ "$ZK_MODE" = docker ] && docker rm -f zkp_bench zkp_ctl > /dev/null 2>&1; return 0; }\n'
         'X() {        # run a command "inside": in the container (docker exec) or directly in the scratch folder (native)\n'
         '  if [ "$ZK_MODE" = native ]; then ( cd "$NH" && env ZHOME="$NH" ZBASE="$NH/base" ZOKRATES="$ZOK_BIN" ZOKRATES_STDLIB="$ZOK_STD" "${DXE[@]}" "$@" )\n'
         '  else docker exec "${DXE[@]}" "$C" "$@"; fi\n'
         '}\n'
         'alive() { [ "$ZK_MODE" = native ] || [ "$(docker inspect -f \'{{.State.Running}}\' "$C" 2>/dev/null)" = true ]; }\n')
t = sub1(t, 'start_container() {\n  docker rm -f "$C" > /dev/null 2>&1\n',
         'start_container() {\n'
         '  if [ "$ZK_MODE" = native ]; then\n'
         '    rm -rf "$NH"; mkdir -p "$NH/base" "$NH/w" || exit 1\n'
         '    for f in zphase.sh zprep.sh; do cp "$f" "$NH/$f" || exit 1; done\n'
         '    for f in circuits/*; do cp "$f" "$NH/base/" || exit 1; done\n'
         '    return 0\n'
         '  fi\n'
         '  docker rm -f "$C" > /dev/null 2>&1\n')
t = sub1(t, '|| { echo "Could not start the container $C. Is Docker Desktop running?"; exit 1; }', '|| { echo "Could not start the container $C. Is Docker running?"; exit 1; }')
# environment capture
new_env = r'''capture_env() {
  {
    echo "# run_remeasure_linux.sh mode=$MODE ZK_MODE=$ZK_MODE REPS=$REPS WARMUP=$WARMUP CONTROL=$CONTROL ONLY='$ONLY' started $(date -u +%FT%TZ) (host clock)"
    [ -n "${RESUME:-}" ] && echo "# RESUMED $(date -u +%FT%TZ)"
    echo "machine label: $(cat .machine 2>/dev/null)"
    capture_env_basic
    if [ "$ZK_MODE" = docker ]; then
      docker version 2>&1 | head -60
      docker image inspect "$IMAGE" --format 'image {{.Id}} created {{.Created}}' 2>/dev/null
      echo "# inside the container"
      docker exec "$C" bash -c 'zokrates --version; echo "binary sha256: $(sha256sum "$(command -v zokrates)" | cut -d" " -f1)"; echo "cpus: $(nproc)"; grep -m1 "model name" /proc/cpuinfo; free -m | sed -n 2p; uname -r' 2>&1
    else
      echo "# native ZoKrates"; "$ZOK_BIN" --version; echo "binary: $ZOK_BIN  sha256: $(zok_sha256 "$ZOK_BIN")  stdlib: $ZOK_STD"
    fi
  } >> "$RES/env.txt" 2>&1
}

'''
t = between(t, "capture_env() {", "prep_ids() {", new_env)
t = sub1(t, 'r=$(docker exec "${DXE[@]}" "$C" bash zprep.sh "$id"', 'r=$(X bash zprep.sh "$id"')
t = sub1(t, 'r=$(docker exec "${DXE[@]}" "$C" bash zphase.sh "w/$id"', 'r=$(X bash zphase.sh "w/$id"')
t = sub1(t, '''[ "$(docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null)" != true ]''', '! alive')
t = sub1(t, '''    echo "pass $rep ($label) end   $(date -u +%FT%TZ)  battery_status(2=AC)=$(ac_state)  cpu_clock_mhz=$(cpu_mhz)  host_free_gb=$(host_free_gb)  c_free_gb=$(free_gb_of /c)" >> "$RES/pass_log.txt"\n''',
         '''    echo "pass $rep ($label) end   $(date -u +%FT%TZ)  battery_status(2=AC)=$(ac_state)  cpu_clock_mhz=$(cpu_mhz)  host_free_gb=$(host_free_gb)  c_free_gb=$(free_gb_of /c)" >> "$RES/pass_log.txt"\n'''
         '''    [ -n "${AFTER_PASS_HOOK:-}" ] && { eval "$AFTER_PASS_HOOK"; } > /dev/null 2>&1      # between passes, outside every timed region\n''')
t = sub1(t, "c_free_gb=$(free_gb_of /c)", "c_free_gb=$(free_gb_of /) load=$(cut -d' ' -f1-3 /proc/loadavg) steal_jiffies=$(awk '/^cpu /{print $9}' /proc/stat)", count=2)
# the long Windows-specific failure messages
t = between(t, '''        echo "!!! The container stopped or its disk failed''', '''        echo "!!! This visit is NOT marked done''',
            '''        echo "!!! The container stopped or the disk failed (Input/output error). Usual causes: the machine was suspended or recycled, the disk is nearly full, or an out-of-memory kill (ECDSA, RSA-4096 need about 4.5 GiB)."\n''')
t = sub1(t, '''        echo "!!! This visit is NOT marked done and will be repeated. Free at least 15 GB on drive $(disk_path | tr -d / | tr a-z A-Z):, restart Docker Desktop, then continue with:  RESUME=$RES bash run_remeasure.sh$MODEARG"; exit 1''',
         '''        echo "!!! This visit is NOT marked done and will be repeated. Free disk space, restart Docker if it stopped, then continue with:  RESUME=$RES bash run_remeasure_linux.sh$MODEARG"; exit 1''')
t = sub1(t, '''        echo "!!! Free space (or move Docker's disk to another drive: README section 5), restart Docker Desktop, then continue with:  RESUME=$RES bash run_remeasure.sh$MODEARG"; exit 1''',
         '''        echo "!!! Free disk space, then continue with:  RESUME=$RES bash run_remeasure_linux.sh$MODEARG"; exit 1''')
t = sub1(t, '''echo; echo "Interrupted. To continue this run:  RESUME=$RES bash run_remeasure.sh$MODEARG"; exit 130''', '''echo; echo "Interrupted. To continue this run:  RESUME=$RES bash run_remeasure_linux.sh$MODEARG"; exit 130''')
# start-up checks
t = sub1(t, 'docker info > /dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop, wait until it says it is running, then run this again."; exit 1; }\nfor f in envlib.sh zphase.sh',
         'if [ "$ZK_MODE" = docker ]; then docker info > /dev/null 2>&1 || { echo "Docker is not running (ZK_MODE=docker). Start it, or use ZK_MODE=native after  bash check_setup_linux.sh"; exit 1; }\n'
         'else "$ZOK_BIN" --version > /dev/null 2>&1 || { echo "ZoKrates binary not found or not runnable at $ZOK_BIN. Run  bash check_setup_linux.sh  first."; exit 1; }; fi\nfor f in envlib_linux.sh zphase.sh')
t = sub1(t, 'echo "Windows Power mode setting (overlay GUID; Best performance = ded574b5-45a0-4f42-8737-46345c09c238): plugged in = $(pm_ac)   on battery = $(pm_dc)"\n',
         'echo "mode: $ZK_MODE   cpus: $(nproc)   $(cpu_name)"\n')
t = sub1(t, 'BINDDIR="$RES/bindctl"; mkdir -p "$BINDDIR"', 'BINDDIR="$RES/bindctl"; mkdir -p "$BINDDIR"; chmod 777 "$BINDDIR"')
# bind-mount control: docker mode only, and only if bind mounts work on this host
t = sub1(t, 'if [ "$CONTROL" = 1 ]; then\n  echo; echo "================ CONTROL: same circuits on a Windows bind mount (the old storage) ================"\n',
         'if [ "$CONTROL" = 1 ] && [ "$ZK_MODE" = docker ]; then\n'
         '  probe=$(mktemp -d "$PWD/probe.XXXXXX") && chmod 777 "$probe" && docker run --rm -v "$probe:/bind" --entrypoint sh "$IMAGE" -c \'touch /bind/t\' > /dev/null 2>&1 && [ -e "$probe/t" ] || { echo "bind mounts do not work on this host: control skipped"; CONTROL=0; }\n'
         '  rm -rf "$probe"\n'
         'fi\n'
         'if [ "$CONTROL" = 1 ] && [ "$ZK_MODE" = docker ]; then\n  echo; echo "================ CONTROL: same circuits on a bind-mounted host folder ================"\n')
t = sub1(t, '''echo "Send back the whole folder $RES (right-click it > Compress to ZIP file, then attach the zip): results.csv, results_bind_control.csv, env.txt, order.txt, pass_log.txt, raw_run.log"''',
         '''echo "Results are in $RES (results.csv, results_bind_control.csv if the control ran, env.txt, order.txt, pass_log.txt, raw_run.log); bash pack_results_linux.sh packs them."''')
wr("run_remeasure_linux.sh", t)

# ---------------------------------------------------------------------------------------------------- run_memory_profile_linux.sh
m = rd("run_memory_profile.sh")
m = sub1(m, "#!/bin/bash\n", "#!/bin/bash\n# LINUX VARIANT (Codespaces, Colab, any Linux machine), derived from run_memory_profile.sh by make_linux_scripts.py. ZK_MODE=docker|native as in run_remeasure_linux.sh.\n")
m = sub1(m, "source ./envlib.sh\n",
         'ZK_MODE=${ZK_MODE:-$(cat .zkmode 2>/dev/null)}; ZK_MODE=${ZK_MODE:-docker}; export ZK_MODE\n'
         'NH=${NATIVE_HOME:-/tmp/zk_native}; ZOK_BIN=${ZOK_BIN:-$PWD/zokrates_bin/zokrates}; ZOK_STD=${ZOK_STD:-$PWD/zokrates_bin/stdlib}\n'
         'source ./envlib_linux.sh\n')
m = sub1(m, 'docker info > /dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop, wait until it says it is running, then run this again."; exit 1; }\n',
         'if [ "$ZK_MODE" = docker ]; then docker info > /dev/null 2>&1 || { echo "Docker is not running (ZK_MODE=docker)."; exit 1; }\n'
         'else "$ZOK_BIN" --version > /dev/null 2>&1 || { echo "ZoKrates binary not found at $ZOK_BIN. Run  bash check_setup_linux.sh  first."; exit 1; }; fi\n')
m = sub1(m, "eval \"$(sed -n '/^CONFIGS=(/,/^)/p' run_remeasure.sh)\"", "eval \"$(sed -n '/^CONFIGS=(/,/^)/p' run_remeasure_linux.sh)\"")
m = sub1(m, "RES=${RESUME:-memory_$(date +%Y%m%d_%H%M%S)}", "RES=${RESUME:-memory_$(date +%Y%m%d_%H%M%S)${MEM_SUFFIX:-}}")
m = sub1(m, "cleanup() { docker rm -f \"$C\" > /dev/null 2>&1; }\n",
         'cleanup() { [ "$ZK_MODE" = docker ] && docker rm -f "$C" > /dev/null 2>&1; return 0; }\n'
         'DXE=()\n'
         'X() { if [ "$ZK_MODE" = native ]; then ( cd "$NH" && env ZHOME="$NH" ZBASE="$NH/base" ZOKRATES="$ZOK_BIN" ZOKRATES_STDLIB="$ZOK_STD" "$@" ); else docker exec "$C" "$@"; fi; }\n'
         'alive() { [ "$ZK_MODE" = native ] || [ "$(docker inspect -f \'{{.State.Running}}\' "$C" 2>/dev/null)" = true ]; }\n')
m = sub1(m, 'docker rm -f "$C" > /dev/null 2>&1\ndocker run -d --name "$C" --entrypoint sleep "$IMAGE" infinity > /dev/null || { echo "Could not start the container. Is Docker Desktop running?"; exit 1; }\n'
            'docker exec "$C" mkdir -p base w || exit 1\n'
            'for f in zprofile.sh zprep.sh; do docker cp "$f" "$C:/home/zokrates/$f" || exit 1; done\n'
            'for f in circuits/*; do docker cp "$f" "$C:/home/zokrates/base/" || exit 1; done\n',
         'if [ "$ZK_MODE" = native ]; then\n'
         '  rm -rf "$NH"; mkdir -p "$NH/base" "$NH/w" || exit 1\n'
         '  for f in zprofile.sh zprep.sh; do cp "$f" "$NH/$f" || exit 1; done\n'
         '  for f in circuits/*; do cp "$f" "$NH/base/" || exit 1; done\n'
         'else\n'
         '  docker rm -f "$C" > /dev/null 2>&1\n'
         '  docker run -d --name "$C" --entrypoint sleep "$IMAGE" infinity > /dev/null || { echo "Could not start the container. Is Docker running?"; exit 1; }\n'
         '  docker exec "$C" mkdir -p base w || exit 1\n'
         '  for f in zprofile.sh zprep.sh; do docker cp "$f" "$C:/home/zokrates/$f" || exit 1; done\n'
         '  for f in circuits/*; do docker cp "$f" "$C:/home/zokrates/base/" || exit 1; done\n'
         'fi\n')
m = sub1(m, 'r=$(docker exec "$C" bash zprep.sh "$id"', 'r=$(X bash zprep.sh "$id"')
m = sub1(m, 'r=$(docker exec "$C" bash zprofile.sh "w/$id"', 'r=$(X bash zprofile.sh "w/$id"')
m = sub1(m, 'docker exec "$C" rm -rf "w/$id" > /dev/null 2>&1', 'X rm -rf "w/$id" > /dev/null 2>&1')
m = sub1(m, '''  if [ "$(docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null)" != true ]; then\n    echo "!!! The container stopped (out of memory is the usual reason). Restart Docker Desktop and continue with:  RESUME=$RES bash run_memory_profile.sh"; exit 1''',
         '''  if ! alive; then\n    echo "!!! The container stopped (out of memory is the usual reason). Restart Docker and continue with:  RESUME=$RES bash run_memory_profile_linux.sh"; exit 1''')
m = sub1(m, 'echo; echo "Interrupted. To continue:  RESUME=$RES bash run_memory_profile.sh"; exit 130', 'echo; echo "Interrupted. To continue:  RESUME=$RES bash run_memory_profile_linux.sh"; exit 130')
wr("run_memory_profile_linux.sh", m)
print("scripts written")
