#!/bin/bash
# Build, then (re)start the Rust agent (:8204) and the Strands coordinator
# (:8209) locally. RUST_AGENT_URL points the coordinator at another Rust agent
# (for example the Lightsail one). Logs and PID files go to logs/.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-stable}"
cargo build --release --bin mersenne-agent
scripts/stop-local.sh
up() { curl -sf --max-time 2 "http://localhost:$1/.well-known/agent-card.json" >/dev/null; }
RUST="${RUST_AGENT_URL:-http://localhost:8204}"
PORT=8204 nohup target/release/mersenne-agent > logs/native.log 2>&1 &
echo $! > logs/native.pid
RUST_AGENT_URL="$RUST" A2A_PORT=8209 nohup python3 coordinator/main.py > logs/coordinator.log 2>&1 &
echo $! > logs/coordinator.pid
for _ in $(seq 1 40); do
  if up 8204 && up 8209; then
    echo "up: 8204 rust agent, 8209 strands coordinator -> $RUST"
    exit 0
  fi
  sleep 0.5
done
echo "failed to start; see logs/" >&2
exit 1
