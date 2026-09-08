#!/bin/bash

progdir="$(cd "$(dirname "$0")" || exit; pwd)"/net_radio

export PYSDL2_DLL_PATH="/usr/lib"

program="python3 ${progdir}/radio.py"
log_file="${progdir}/log.txt"

$program $@ > "$log_file" 2>&1
