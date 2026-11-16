# Shared helpers for the Linux variant (GitHub Codespaces, Google Colab, any Linux machine). Same function names as envlib.sh (Windows).
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
