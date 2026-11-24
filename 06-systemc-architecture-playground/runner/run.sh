#!/bin/bash
set -eu
cd /tmp
printf '[build] Compiling C++ / SystemC...\n'
g++ -std=c++17 -O0 -Wall -Wextra -I/opt/lab /input/*.cpp -o /tmp/model -lsystemc -pthread
printf '[build] OK\n'
set +e
/tmp/model "$@"
rc=$?
set -e
if [ -f /tmp/trace.vcd ]; then
  printf '\n@@VCD_BEGIN@@\n'
  cat /tmp/trace.vcd
  printf '\n@@VCD_END@@\n'
fi
exit "$rc"
