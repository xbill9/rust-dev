#!/bin/bash
# A tour of the a2a CLI against this rig, recorded verbatim for the README and
# articles: echo server, the native Rust agent, the exec-wrapped Rust program,
# task commands, and the ADK coordinator. Transcript -> results/cli-tour-<stamp>.md
# Echo server uses port 8108.
set -uo pipefail
cd "$(dirname "$0")/.."
scripts/start-adk.sh >/dev/null
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="results/cli-tour-$stamp.md"
run() { # run a command, record "$ cmd" and its output
  { printf '\n```console\n$ %s\n' "$*"; eval "$@" 2>&1; printf '```\n'; } | tee -a "$out"
}
note() { printf '\n%s\n' "$*" | tee -a "$out"; }
echo "# a2a CLI tour ($stamp)" > "$out"

note "## Install check"
run a2a version

note "## Echo server (Step 1 of the CLI introduction)"
a2a server --echo --port 8108 --quiet > logs/echo.log 2>&1 &
ECHO=$!; trap 'kill $ECHO 2>/dev/null' EXIT
for _ in $(seq 1 20); do curl -sf --max-time 1 http://localhost:8108/.well-known/agent-card.json >/dev/null && break; sleep 0.25; done
run a2a send -a http://localhost:8108 '"hello world from A2A"'

note "## The native Rust agent (official a2a-rs SDK)"
run a2a card get -a http://localhost:8104
run a2a send -a http://localhost:8104 '"Calculate the first 12 Mersenne primes"'
run a2a send -a http://localhost:8104 --stream '"first 8"'
run a2a send -a http://localhost:8104 --transport rest '"first 4"'
run a2a send -a http://localhost:8104 --data-part "'{\"count\": 6}'"
run "a2a send -a http://localhost:8104 -o json 'first 3' | python3 -c 'import sys,json; t=json.load(sys.stdin)[\"task\"]; print(t[\"status\"][\"state\"], [p for a in t[\"artifacts\"] for p in a[\"parts\"] if \"data\" in p][0][\"data\"])'"

note "## Task commands"
tid=$(a2a send -a http://localhost:8104 -o json 'first 20' | python3 -c 'import sys,json; print(json.load(sys.stdin)["task"]["id"])')
run a2a task get -a http://localhost:8104 "$tid"
run "a2a task list -a http://localhost:8104 | head -12"
note "\`--async\` returns while the task is still working; \`task get --wait\` polls it to completion."
run a2a send -a http://localhost:8104 --async '"first 25"'
aid=$(grep '^Task:' "$out" | tail -1 | awk '{print $2}')
run a2a task get -a http://localhost:8104 "$aid"
run a2a task get -a http://localhost:8104 "$aid" --wait --poll-interval 500ms

note "## The same Rust code, A2A-unaware, served by a2a server --exec (Steps 3-4)"
run "echo 'first 5' | target/release/mersenne-exec"
run a2a card get -a http://localhost:8105
run a2a send -a http://localhost:8105 '"Calculate the first 12 Mersenne primes"'
run a2a send -a http://localhost:8105 --stream '"first 8"'

note "## The ADK coordinator (adk api_server --a2a), same CLI"
CARD=http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
run a2a card get -a $CARD
run a2a send -a $CARD --timeout 120s '"Find the first 9 Mersenne primes with the exec agent"'
note "A benchmark request goes through the run_benchmark tool. The reply is saved as JSON, then the tool call, the answer and the check are printed."
a2a send -a $CARD --timeout 300s -o json "Benchmark both agents for N=3 to 6 with 2 reps" > "results/cli-tour-$stamp-adk-bench.json"
run "python3 -c 'import json,sys; t=json.load(open(sys.argv[1]))[\"task\"]; [print(\"[tool call]\", json.dumps(p[\"data\"][\"args\"])) for m in t[\"history\"] for p in m[\"parts\"] if isinstance(p.get(\"data\"), dict) and \"args\" in p[\"data\"]]; print(t[\"artifacts\"][-1][\"parts\"][0][\"text\"])' results/cli-tour-$stamp-adk-bench.json"
run scripts/check-adk-reply.py "results/cli-tour-$stamp-adk-bench.json" 3 6 2
echo; echo "transcript: $out"
