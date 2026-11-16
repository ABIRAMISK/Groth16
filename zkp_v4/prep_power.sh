#!/bin/bash
# Turns off the screen-off timer, sleep, hibernate and lid-close sleep for the PLUGGED-IN state of the current power plan on this computer. Run once per machine before a long session.
# Windows suspending the computer can break Docker's disk (Input/output error) and stop the run. Never close the lid during a run.
# To undo: Settings > System > Power & battery (sleep timers) and Control Panel > Power Options > Choose what closing the lid does.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")" || exit 1
source ./envlib.sh
powercfg.exe /change monitor-timeout-ac 0 < /dev/null
powercfg.exe /change standby-timeout-ac 0 < /dev/null
powercfg.exe /change hibernate-timeout-ac 0 < /dev/null
powercfg.exe /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 < /dev/null
powercfg.exe /setactive SCHEME_CURRENT < /dev/null
echo "Now:"; power_summary
if [ "$SLEEP_BAD" = 1 ]; then echo "!!! A setting did not change (administrator rights may be needed). Set it by hand: Settings > System > Power & battery > Screen, sleep & hibernate timeouts > Screen and Sleep (plugged in) = Never; Control Panel > Power Options > Choose what closing the lid does > Plugged in = Do nothing."; exit 1; fi
echo "OK: the screen stays on and sleep, hibernate and lid-close sleep are off while plugged in."
