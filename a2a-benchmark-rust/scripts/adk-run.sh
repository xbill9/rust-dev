#!/bin/bash
# adk run: one query, or an interactive session with no argument.
#   scripts/adk-run.sh "Use the native agent to find the first 12 Mersenne primes"
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/adk-env.sh
cd adk
exec adk run rust_bench "$@"
