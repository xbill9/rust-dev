#!/bin/bash
# adk web: ADK dev UI for the rust_bench coordinator on :8107.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/adk-env.sh
exec adk web --port "${ADK_WEB_PORT:-8107}" adk
