#!/bin/bash
# Stop the local agents started by start-local.sh, by PID file. (No pkill -f:
# a pattern naming these programs also matches any shell whose command line
# contains it.)
cd "$(dirname "$0")/.."
for f in logs/native.pid logs/coordinator.pid; do
  [ -f "$f" ] || continue
  pid=$(cat "$f")
  if kill "$pid" 2>/dev/null; then
    while kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
  fi
  rm -f "$f"
done
exit 0
