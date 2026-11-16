#!/bin/bash
# ONE command for a Linux machine: checks the machine, then starts the whole measurement in the background (it keeps running if the terminal is closed) and returns.
#   bash start_linux.sh          full session (about 2.5-4 hours, depending on the machine)
#   bash start_linux.sh quick    10-minute functional check first
# Watch it with  bash status_linux.sh ; if it is interrupted, run this command again and it continues.
cd "$(dirname "$0")" || exit 1
if pgrep -f run_all_linux.sh > /dev/null 2>&1; then echo "A run is already in progress. Watch it with:  bash status_linux.sh"; exit 0; fi
bash check_setup_linux.sh < /dev/null || exit 1
nohup setsid bash run_all_linux.sh "$@" >> run_all.out 2>&1 < /dev/null &
sleep 2; echo "started in the background (pid $!). Watch it with:  bash status_linux.sh"
