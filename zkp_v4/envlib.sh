# Shared helpers (Git Bash, Windows). Sourced by check_setup.sh, run_remeasure.sh, run_memory_profile.sh and pack_results.sh.
export MSYS_NO_PATHCONV=1      # Git Bash must not rewrite arguments such as /c, /getactivescheme or /home/zokrates/... into Windows paths
ps_()     { powershell.exe -NoProfile -NonInteractive -Command "$1" 2>/dev/null < /dev/null | tr -d '\r'; }
ac_state(){ ps_ '(Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus'; }   # 2 = on AC power, 1 = on battery, empty = no battery (desktop PC)
cpu_mhz() { ps_ '(Get-CimInstance Win32_Processor | Select-Object -First 1).CurrentClockSpeed'; }
cpu_name(){ ps_ '(Get-CimInstance Win32_Processor | Select-Object -First 1).Name'; }
os_info() { ps_ "\$o = Get-CimInstance Win32_OperatingSystem; ('{0} version {1}' -f \$o.Caption, \$o.Version)"; }
cores()   { ps_ "\$p = Get-CimInstance Win32_Processor; ('{0} cores, {1} threads' -f (\$p | Measure-Object NumberOfCores -Sum).Sum, (\$p | Measure-Object NumberOfLogicalProcessors -Sum).Sum)"; }
sys_model(){ ps_ "\$c = Get-CimInstance Win32_ComputerSystem; ('{0} {1}; RAM {2} GiB; PCSystemType={3} (1 desktop, 2 laptop)' -f \$c.Manufacturer, \$c.Model, [math]::Round(\$c.TotalPhysicalMemory/1GB,1), \$c.PCSystemType)"; }
pm_ac()   { ps_ '(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes).ActiveOverlayAcPowerScheme'; }
pm_dc()   { ps_ '(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes).ActiveOverlayDcPowerScheme'; }
pq()            { powercfg.exe /query SCHEME_CURRENT "$1" "$2" 2>/dev/null < /dev/null | tr -d '\r' | sed -n 's/.*Current AC Power Setting Index: *0x\([0-9a-fA-F]*\).*/\1/p' | head -1; }   # plugged-in value of a power setting, hex
power_events()  { ps_ "Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Kernel-Power';StartTime=(Get-Date).AddHours(-${1:-14})} -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id | Format-Table -AutoSize"; }   # Id 42 = went to sleep, 107 = woke up
# prints the plugged-in sleep settings; sets SLEEP_BAD=1 if the screen-off timer, sleep, hibernate or lid-close sleep is still on
power_summary() {
  local sl hb lid vid; SLEEP_BAD=0
  sl=$(pq SUB_SLEEP STANDBYIDLE); hb=$(pq SUB_SLEEP HIBERNATEIDLE); lid=$(pq SUB_BUTTONS LIDACTION); vid=$(pq SUB_VIDEO VIDEOIDLE)
  [ -n "$vid" ] && { echo "screen-off timer when plugged in: $((16#$vid)) s (0 = never; on Modern Standby laptops the screen turning off puts the computer into standby)"; [ $((16#$vid)) -ne 0 ] && SLEEP_BAD=1; }
  [ -n "$sl" ]  && { echo "sleep timer when plugged in: $((16#$sl)) s (0 = never)";  [ $((16#$sl)) -ne 0 ]  && SLEEP_BAD=1; }
  [ -n "$hb" ]  && { echo "hibernate timer when plugged in: $((16#$hb)) s (0 = never)"; [ $((16#$hb)) -ne 0 ] && SLEEP_BAD=1; }
  [ -n "$lid" ] && { echo "closing the lid when plugged in: action $((16#$lid)) (0 = do nothing, 1 = sleep)"; [ $((16#$lid)) -ne 0 ] && SLEEP_BAD=1; }
  return 0
}
# Where Docker keeps its virtual disk: the "DataFolder" entry in Docker Desktop's settings (written when the disk is moved in Settings > Resources > Advanced). Empty = default place, under C:\Users\<you>\AppData\Local\Docker
docker_data_dir() {
  local a f d; a=$(cygpath -u "${APPDATA:-}" 2>/dev/null)
  for f in "$a/Docker/settings-store.json" "$a/Docker/settings.json"; do
    [ -n "$a" ] && [ -f "$f" ] || continue
    d=$(tr -d '\r' < "$f" | sed -n 's/.*"[Dd]ataFolder" *: *"\([^"]*\)".*/\1/p' | head -1 | sed 's/\\\\/\//g; s/\\/\//g')
    [ -n "$d" ] && { echo "$d"; return 0; }
  done
  return 0
}
# the drive that holds Docker's virtual disk, written as Git Bash does (/c, /d, ...); DISKPATH=/d in front of a command overrides the detection
disk_path() {
  local l
  [ -n "${DISKPATH:-}" ] && { echo "$DISKPATH"; return 0; }
  l=$(docker_data_dir | sed -n 's/^\([A-Za-z]\):.*/\1/p' | tr 'A-Z' 'a-z')
  [ -n "$l" ] && echo "/$l" || echo "/c"
}
free_gb_of()    { df -k "$1" 2>/dev/null | awk 'NR==2{printf "%.1f", $4/1048576}'; }   # free space on a drive in GB
host_free_gb()  { free_gb_of "$(disk_path)"; }                                          # free space on the drive that holds Docker's virtual disk
# returns 0 and prints the reason when a drive is too full to go on (Docker's drive under 3 GB, or C: under 1 GB); returns 1 when all is well
disk_low() {
  local dp fg cg; dp=$(disk_path); fg=$(free_gb_of "$dp"); cg=$(free_gb_of /c)
  if [ -n "$fg" ] && awk -v f="$fg" 'BEGIN{exit !(f+0<3)}'; then echo "only ${fg} GB free on drive $(echo "${dp#/}" | tr a-z A-Z):, where Docker's virtual disk lives"; return 0; fi
  if [ "$dp" != /c ] && [ -n "$cg" ] && awk -v f="$cg" 'BEGIN{exit !(f+0<1)}'; then echo "only ${cg} GB free on drive C:, which Windows and Docker Desktop need"; return 0; fi
  return 1
}
# drive letters, file systems, which physical disk each drive is on, and the type of every disk (SSD/HDD, NVMe/SATA/USB): goes into env.txt
disk_info() {
  ps_ "Get-Volume | Where-Object DriveLetter | Sort-Object DriveLetter | Format-Table DriveLetter,FileSystem,DriveType,@{n='SizeGB';e={[int](\$_.Size/1GB)}},@{n='FreeGB';e={[math]::Round(\$_.SizeRemaining/1GB,1)}} -AutoSize | Out-String -Width 200; Get-Partition | Where-Object DriveLetter | Sort-Object DriveLetter | Format-Table DriveLetter,DiskNumber -AutoSize | Out-String -Width 200; Get-PhysicalDisk | Sort-Object DeviceId | Format-Table DeviceId,FriendlyName,MediaType,BusType,@{n='SizeGB';e={[int](\$_.Size/1GB)}} -AutoSize | Out-String -Width 200"
}
docker_cpus()    { docker info 2>/dev/null | awk '/ CPUs:/{print $2; exit}'; }
docker_mem_gib() { docker info 2>/dev/null | awk '/Total Memory/{v=$3; if (v ~ /MiB/) {sub(/MiB/,"",v); v=v/1024} else {sub(/GiB/,"",v)} printf "%.1f", v; exit}'; }
# short label of the CPU, e.g. "Intel(R) Core(TM) i7-8665U CPU @ 1.90GHz" -> i7-8665U ; falls back to the computer name
machine_tag() {
  local t; t=$(cpu_name | sed -E 's/\((R|TM)\)//g; s/@.*//; s/[[:space:]]+CPU//; s/with Radeon.*//; s/(Intel|Core|AMD|Processor)//g; s/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]+/-/g; s/[^A-Za-z0-9-]//g')
  [ -n "$t" ] || t=$(hostname | tr -cd 'A-Za-z0-9-')
  echo "$t"
}
capture_env_basic() {
  echo "# captured $(date -u +%FT%TZ) (host clock)"
  echo "# host"; uname -a; echo "os: $(os_info)"
  echo "cpu: $(cpu_name)  ($(cores))   clock_mhz=$(cpu_mhz)"
  echo "system: $(sys_model)"
  powercfg.exe /getactivescheme 2>/dev/null < /dev/null | tr -d '\r'
  echo "battery_status(2=AC,1=battery,empty=no battery)=$(ac_state)"
  echo "power_mode_overlay_guid plugged_in=$(pm_ac)  on_battery=$(pm_dc)   (Best performance = ded574b5-45a0-4f42-8737-46345c09c238)"
  echo "# wsl"; wsl.exe --version 2>/dev/null < /dev/null | tr -d '\0\r'
  echo "# docker"; docker --version; docker info 2>/dev/null | grep -E "CPUs|Total Memory|Operating System|Kernel Version|Server Version"
  echo "# disks"; disk_info
  echo "docker data folder: $(docker_data_dir)  [empty = default place on C:]  free-space drive: $(disk_path)  free_gb=$(host_free_gb)"
}
