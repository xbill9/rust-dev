#!/bin/bash
# Native A2A v1.0 agent (official a2a-rs SDK) on port 8104.
set -euo pipefail
cd "$(dirname "$0")/.."
cargo build --release --bin mersenne-agent
PORT="${PORT:-8104}" exec target/release/mersenne-agent
