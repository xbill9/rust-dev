#!/bin/bash
# Repeated ADK checks against the live coordinator (calls Gemini RUNS*2 times).
#  1. benchmark requests with varied ranges: check-adk-reply.py must PASS
#  2. "Calculate the first N" with no agent named: must route to native_rust_agent
# Writes logs/adk-reliability/ and results/adk-reliability-<stamp>.json.
set -euo pipefail
cd "$(dirname "$0")/.."
RUNS="${RUNS:-10}"
CARD=http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
curl -sf --max-time 2 "$CARD" >/dev/null || scripts/start-adk.sh
. scripts/adk-env.sh
dir=logs/adk-reliability; rm -rf "$dir"; mkdir -p "$dir" results
for i in $(seq 1 "$RUNS"); do
  lo=$(( (i % 4) + 1 )); hi=$(( lo + 2 + (i % 5) )); r=$(( (i % 3) + 1 ))
  a2a send -a "$CARD" --timeout 300s -o json "Benchmark both agents for N=$lo to $hi with $r reps" > "$dir/bench-$i.json" 2>&1 || true
  if scripts/check-adk-reply.py "$dir/bench-$i.json" "$lo" "$hi" "$r" > "$dir/bench-$i.check" 2>&1; then echo "bench $i PASS"; else echo "bench $i FAIL"; fi
  a2a send -a "$CARD" --timeout 120s -o json "Calculate the first $((i + 10)) Mersenne primes" > "$dir/route-$i.json" 2>&1 || true
done
python3 - "$dir" "$RUNS" "$MODEL_NAME" <<'PY'
import json, sys, glob, datetime
d, runs, model = sys.argv[1], int(sys.argv[2]), sys.argv[3]
bench_pass = sum(open(f).read().strip().endswith("PASS") for f in glob.glob(f"{d}/bench-*.check"))
routes = []
for f in sorted(glob.glob(f"{d}/route-*.json")):
    try:
        t = json.load(open(f))["task"]
        names = [p["data"]["args"].get("agent_name") for m in t.get("history", []) for p in m["parts"]
                 if isinstance(p.get("data"), dict) and p["data"].get("name") == "transfer_to_agent" and "args" in p["data"]]
        routes.append(names[0] if names else "(none)")
    except Exception as e:
        routes.append(f"(error: {e.__class__.__name__})")
out = {"model": model, "runs": runs, "bench_checks_passed": bench_pass,
       "routed_to_native": routes.count("native_rust_agent"), "routes": routes}
stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
json.dump(out, open(f"results/adk-reliability-{stamp}.json", "w"), indent=2)
print(json.dumps({k: v for k, v in out.items() if k != "routes"}))
PY
