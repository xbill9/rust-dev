#!/bin/bash
# Drive every agent with the same a2a CLI commands and check each reply.
#   scripts/test-cli.sh                 local only (starts both local agents)
#   scripts/test-cli.sh lightsail       the Rust agent on Lightsail
#   scripts/test-cli.sh agentcore       the Strands coordinator on AgentCore Runtime
#   scripts/test-cli.sh all             local + lightsail + agentcore
# AWS URLs and the Cognito user come from .aws-state.json (written by the
# deploy scripts).
set -euo pipefail
cd "$(dirname "$0")/.."
command -v a2a >/dev/null || { echo "a2a CLI not on PATH (see README)"; exit 1; }
targets=("${@:-local}")
[ "${targets[0]}" = all ] && targets=(local lightsail agentcore)
fail=0
ok() { echo "✅ $1"; }
bad() { echo "❌ $1"; [ -n "${2:-}" ] && echo "$2"; fail=1; }
expect() { # label pattern output
  if grep -q "$2" <<<"$3"; then ok "$1"; else bad "$1" "$3"; fi
}

rust_checks() { # name url
  local name=$1 url=$2 o
  echo "== $name rust agent ($url)"
  o=$(a2a card get -a "$url"); echo "$o" | head -6
  expect "$name card (A2A v1.0)" "A2A v1.0" "$o"
  expect "$name send" "Found first 5 Mersenne primes" "$(a2a send -a "$url" "Calculate the first 5 Mersenne primes")"
  expect "$name stream" "Found first 8 Mersenne primes" "$(a2a send -a "$url" --stream "first 8")"
  expect "$name rest" "Found first 4 Mersenne primes" "$(a2a send -a "$url" --transport rest "first 4")"
  expect "$name data-part" "Found first 6 Mersenne primes" "$(a2a send -a "$url" --data-part '{"count": 6}')"
}

coordinator_checks() { # name url [extra a2a flags...]
  local name=$1 url=$2 o; shift 2
  echo "== $name strands coordinator ($url)"
  o=$(a2a "$@" card get -a "$url"); echo "$o" | head -6
  expect "$name card (A2A v0.3)" "A2A v0.3" "$o"
  expect "$name send" "Found first 7 Mersenne primes" "$(a2a "$@" --timeout 120s send -a "$url" "Find the first 7 Mersenne primes")"
  expect "$name stream" "Found first 11 Mersenne primes" "$(a2a "$@" --timeout 120s send -a "$url" --stream "first 11 Mersenne primes")"
}

state() { python3 scripts/aws_state.py get "$1"; }

for t in "${targets[@]}"; do
  case $t in
    local)
      scripts/start-local.sh
      rust_checks local http://localhost:8204
      coordinator_checks local http://localhost:8209
      ;;
    lightsail)
      rust_checks lightsail "$(state lightsail_url)"
      ;;
    agentcore)
      token=$(python3 scripts/cognito-token.py)
      # AgentCore wants a session id of at least 33 characters per session.
      session="a2a-cli-$(cat /proc/sys/kernel/random/uuid)"
      coordinator_checks agentcore "$(state agentcore_card)" \
        --auth "Bearer $token" --svc-param "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=$session"
      ;;
    *) echo "unknown target $t"; exit 2 ;;
  esac
done
exit $fail
