#!/bin/bash
# Start whichever of the two agents is not already answering. Logs go to logs/.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
cargo build --release
up() { curl -sf --max-time 2 "http://localhost:$1/.well-known/agent-card.json" >/dev/null; }
up 8104 || { nohup scripts/serve-native.sh > logs/native.log 2>&1 & }
up 8105 || { nohup scripts/serve-exec.sh  > logs/exec.log   2>&1 & }
for _ in $(seq 1 30); do up 8104 && up 8105 && { echo "agents up: 8104 native, 8105 exec"; exit 0; }; sleep 0.5; done
echo "agents failed to start; see logs/" >&2; exit 1
