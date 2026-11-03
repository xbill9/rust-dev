#!/bin/bash
# adk api_server --a2a: serves the rust_bench coordinator as an A2A v1.0 agent.
#   card:     http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
#   JSON-RPC: http://localhost:8106/a2a/rust_bench
# Must run from the rig root: ADK resolves the agents dir against the cwd.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/adk-env.sh
exec adk api_server --a2a --port "${ADK_PORT:-8106}" adk
