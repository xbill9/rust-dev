#!/bin/bash
# (Re)start the Rust agents and the ADK A2A server. Logs in logs/.
set -euo pipefail
cd "$(dirname "$0")/.."
scripts/start-all.sh
CARD=http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
pkill -f "adk api_server --a2a --port 8106" || true
for _ in $(seq 1 20); do curl -sf --max-time 1 "$CARD" >/dev/null || break; sleep 0.25; done
nohup scripts/serve-adk.sh > logs/adk.log 2>&1 &
for _ in $(seq 1 60); do curl -sf --max-time 1 "$CARD" >/dev/null && { echo "adk up: 8106"; exit 0; }; sleep 0.5; done
echo "adk failed to start; see logs/adk.log" >&2; exit 1
