#!/bin/sh
# c.sh <label> <jlink args...>: one container step, timed, output kept
W="U:/Temp/claude/fc7188587c3dafc5/3d867fd0-f607-49be-a9cf-69b154f6ec6b/scratchpad/jlink70"
label=$1; shift
start=$(date +%s.%N)
MSYS_NO_PATHCONV=1 docker run --rm -v "$W/img:/work:ro" -v "$W/out:/out" etb-bench jlink --resource jlink://host.docker.internal:2331 --device nRF52840_xxAA "$@" > "$W/out/$label.txt" 2>&1
rc=$?
end=$(date +%s.%N)
echo "$label rc=$rc s=$(python -c "print(round($end-$start,2))")" | tee -a "$W/out/timings.txt"
cat "$W/out/$label.txt"
