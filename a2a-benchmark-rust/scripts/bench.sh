#!/bin/bash
# Full benchmark, N=1..22, 5 reps each, both Rust agents. Results -> results/.
#   ADK=1 adds a third series: the same requests sent to the ADK coordinator
#   (adk api_server --a2a, Gemini), which routes them to the native agent.
set -euo pipefail
cd "$(dirname "$0")/.."
agents=(--agent native=http://localhost:8104 --agent exec=http://localhost:8105)
if [ "${ADK:-0}" = 1 ]; then
  scripts/start-adk.sh
  agents+=(--agent adk=http://localhost:8106/a2a/rust_bench)
else
  scripts/start-all.sh
fi
mkdir -p results
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target/release/mersenne-bench --min "${MIN:-1}" --max "${MAX:-22}" --reps "${REPS:-5}" \
  --out "results/bench-$stamp.json" "${agents[@]}" "$@" | tee "results/bench-$stamp.md"
