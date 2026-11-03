#!/bin/bash
# Step 3 of the A2A CLI introduction: the a2a CLI serves an A2A-unaware
# program. mersenne-exec reads stdin and prints to stdout; `a2a server --exec`
# turns that into an A2A v1.0 agent on port 8105.
set -euo pipefail
cd "$(dirname "$0")/.."
cargo build --release --bin mersenne-exec
exec a2a server --exec "$PWD/target/release/mersenne-exec" --chunk=$'\n' \
  --name "Mersenne Prime Exec Rust" \
  --description "mersenne-exec (Rust, A2A-unaware) wrapped by a2a server --exec" \
  --advertise-address "http://localhost:${PORT:-8105}" \
  --port "${PORT:-8105}" --quiet
