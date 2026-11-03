#!/bin/bash
# Stop the Rust agents and the ADK server. --rust-only leaves ADK running
# (start-all.sh uses it so bench/test runs do not take ADK down).
pkill -f target/release/mersenne-agent || true
pkill -f "a2a server --exec .*mersenne-exec" || true
[ "${1:-}" = "--rust-only" ] || pkill -f "adk api_server --a2a --port 8106" || true
