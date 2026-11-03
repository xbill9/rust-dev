#!/bin/bash
# ADK CLI checks: adk run, then the a2a CLI talking to `adk api_server --a2a`,
# which delegates over A2A to the Rust agents. Needs Gemini (scripts/adk-env.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
command -v adk >/dev/null || { echo "adk not on PATH: pip install 'google-adk[a2a]'"; exit 1; }
scripts/start-adk.sh
CARD=http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
mkdir -p logs
fail=0
pass() { echo "✅ $1"; }
miss() { echo "❌ $1"; shift; printf '%s\n' "$@"; fail=1; }

o=$(scripts/adk-run.sh "Use the native agent to find the first 12 Mersenne primes" 2>/dev/null)
grep -q "Found first 12 Mersenne primes" <<<"$o" && pass "adk run -> native" || miss "adk run -> native" "$o"

a2a card get -a "$CARD" | grep -q "rust_bench" && pass "a2a card get (adk)" || miss "a2a card get (adk)"

o=$(a2a send -a "$CARD" --timeout 120s "Use the native agent to find the first 11 Mersenne primes")
grep -q "Found first 11 Mersenne primes" <<<"$o" && pass "a2a send -> adk -> native" || miss "a2a send -> adk -> native" "$o"

o=$(a2a send -a "$CARD" --timeout 120s "Find the first 9 Mersenne primes with the exec agent")
grep -q "Found first 9 Mersenne primes" <<<"$o" && pass "a2a send -> adk -> exec" || miss "a2a send -> adk -> exec" "$o"

o=$(a2a send -a "$CARD" --timeout 120s --stream "first 7 with the native agent")
grep -q "Found first 7 Mersenne primes" <<<"$o" && pass "a2a send --stream -> adk -> native" || miss "stream" "$o"

a2a send -a "$CARD" --timeout 300s -o json "Benchmark both agents for N=3 to 6 with 2 reps" > logs/adk-bench-reply.json
if scripts/check-adk-reply.py logs/adk-bench-reply.json 3 6 2; then pass "adk run_benchmark: args and quoted numbers"
else miss "adk run_benchmark: args and quoted numbers"; fi
exit $fail
