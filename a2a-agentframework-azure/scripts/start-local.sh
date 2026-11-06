#!/bin/bash
# Build, then (re)start the Rust agent (:8304) and the Agent Framework
# coordinator (:8309) locally. RUST_AGENT_URL points the coordinator at another
# Rust agent (for example the Container Apps one). Logs and PID files go to logs/.
#
# The coordinator needs a2a-sdk 1.x; the shared Python carries 0.3 for the
# Strands rig. Its packages go into build/local-site (pip --target, refreshed
# when coordinator/requirements.txt changes) and reach Python via PYTHONPATH.
# The model endpoint comes from .azure-state.json (scripts/deploy-model.py).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs build
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-stable}"
cargo build --release --bin mersenne-agent
stamp=build/local-site/.requirements.sha256
want=$(sha256sum coordinator/requirements.txt | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null)" != "$want" ]; then
  rm -rf build/local-site
  # pip compares the target dir against the shared site and prints resolver
  # conflicts that do not apply to it; keep them out of the terminal.
  python3 -m pip install -q --disable-pip-version-check --target build/local-site \
    -r coordinator/requirements.txt > logs/pip-local-site.log 2>&1 \
    || { cat logs/pip-local-site.log; exit 1; }
  echo "$want" > "$stamp"
fi
endpoint="${AZURE_OPENAI_ENDPOINT:-$(python3 scripts/azure_state.py get openai_endpoint)}"
scripts/stop-local.sh
up() { curl -sf --max-time 2 "http://localhost:$1/.well-known/agent-card.json" >/dev/null; }
RUST="${RUST_AGENT_URL:-http://localhost:8304}"
PORT=8304 nohup target/release/mersenne-agent > logs/native.log 2>&1 &
echo $! > logs/native.pid
PYTHONPATH=build/local-site RUST_AGENT_URL="$RUST" AZURE_OPENAI_ENDPOINT="$endpoint" PORT=8309 \
  nohup python3 coordinator/main.py > logs/coordinator.log 2>&1 &
echo $! > logs/coordinator.pid
for _ in $(seq 1 60); do
  if up 8304 && up 8309; then
    echo "up: 8304 rust agent, 8309 agent framework coordinator -> $RUST"
    exit 0
  fi
  sleep 0.5
done
echo "failed to start; see logs/" >&2
exit 1
