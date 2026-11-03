#!/bin/bash
# Full benchmark, N=1..22, 5 reps each, both agents. Results -> results/.
set -euo pipefail
cd "$(dirname "$0")/.."
scripts/start-all.sh
mkdir -p results
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target/release/mersenne-bench --min "${MIN:-1}" --max "${MAX:-22}" --reps "${REPS:-5}" \
  --out "results/bench-$stamp.json" "$@" | tee "results/bench-$stamp.md"
