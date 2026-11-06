#!/bin/bash
# Drive every agent with the same a2a CLI commands and check each reply.
#   scripts/test-cli.sh                    local only (starts both local agents)
#   scripts/test-cli.sh aca-rust           the Rust agent on Azure Container Apps
#   scripts/test-cli.sh aca-coordinator    the Agent Framework coordinator on Container Apps
#   scripts/test-cli.sh all                local + aca-rust + aca-coordinator
# Azure URLs come from .azure-state.json (written by the deploy scripts); the
# coordinator's bearer token from scripts/entra-token.py (your az login).
set -euo pipefail
cd "$(dirname "$0")/.."
command -v a2a >/dev/null || { echo "a2a CLI not on PATH (see README)"; exit 1; }
targets=("${@:-local}")
[ "${targets[0]}" = all ] && targets=(local aca-rust aca-coordinator)
fail=0
ok() { echo "✅ $1"; }
bad() { echo "❌ $1"; [ -n "${2:-}" ] && echo "$2"; fail=1; }
expect() { # label pattern output
  if grep -q "$2" <<<"$3"; then ok "$1"; else bad "$1" "$3"; fi
}
once() { # label pattern output: the reply line appears exactly once
  local n; n=$(grep -o "$2" <<<"$3" | wc -l)
  if [ "$n" = 1 ]; then ok "$1"; else bad "$1 (seen $n times)" "$3"; fi
}
undoubled() { # label pattern output: present, and never run on from a previous copy
  # (a stream shows the reply per artifact event; "...61Found first" is one
  # artifact holding it twice)
  if grep -q "$2" <<<"$3" && ! grep -q "[0-9]$2" <<<"$3"; then ok "$1"; else bad "$1" "$3"; fi
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
  echo "== $name agent framework coordinator ($url)"
  o=$(a2a "$@" card get -a "$url"); echo "$o" | head -6
  expect "$name card (A2A v1.0)" "A2A v1.0" "$o"
  once "$name send" "Found first 7 Mersenne primes" "$(a2a "$@" --timeout 120s send -a "$url" "Find the first 7 Mersenne primes")"
  undoubled "$name stream" "Found first 11 Mersenne primes" "$(a2a "$@" --timeout 120s send -a "$url" --stream "first 11 Mersenne primes")"
  once "$name rest" "Found first 3 Mersenne primes" "$(a2a "$@" --timeout 120s send -a "$url" --transport rest "Find the first 3 Mersenne primes")"
}

state() { python3 scripts/azure_state.py get "$1"; }

for t in "${targets[@]}"; do
  case $t in
    local)
      scripts/start-local.sh
      rust_checks local http://localhost:8304
      coordinator_checks local http://localhost:8309
      ;;
    aca-rust)
      url=$(state rust_url)
      rust_checks aca-rust "$url"
      ;;
    aca-coordinator)
      url=$(state coordinator_url)
      echo "-- without a token (expect 401)"
      code=$(curl -s -o /dev/null -w '%{http_code}' "$url/.well-known/agent-card.json")
      if [ "$code" = 401 ]; then ok "aca-coordinator rejects no token ($code)"; else bad "aca-coordinator rejects no token" "got HTTP $code"; fi
      coordinator_checks aca-coordinator "$url" --auth "Bearer $(python3 scripts/entra-token.py)"
      ;;
    *) echo "unknown target $t"; exit 2 ;;
  esac
done
exit $fail
