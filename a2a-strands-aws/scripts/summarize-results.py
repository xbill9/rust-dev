#!/usr/bin/env python3
"""Print the figures the article quotes, computed from results/cli-bench-*.json.

  scripts/summarize-results.py > results/summary-20261105.txt

Wall times print to 0.1 ms, compute times to 4 significant figures. The
platform differences (AWS median minus localhost median) are computed here.
"""

import json
from pathlib import Path

RIG = Path(__file__).resolve().parents[1]
files = sorted((RIG / "results").glob("cli-bench-*.json"))
med = {}
for f in files:
    d = json.loads(f.read_text())
    session = d.get("agentcore_session")
    print(f"## {f.name}: N={d['n']}, {d['reps']} reps per target, {d['a2a']}"
          + (f", AgentCore session {session}" if session else ""))
    for name, t in d["targets"].items():
        w, c = t["wall_ms"], t["compute_ms"]
        line = (f"{name}: ok {t['ok']}/{t['calls']}, wall median {w['median']:.1f} ms "
                f"(min {w['min']:.1f}, max {w['max']:.1f})")
        if c:
            line += f", compute median {c['median']:.4g} ms (min {c['min']:.4g}, max {c['max']:.4g})"
        print(line)
        key = f"{name} [{session}]" if session else name
        med[key] = w["median"]
    print()


def diff(a: str, b: str) -> None:
    if a in med and b in med:
        print(f"{a} minus {b}: {med[a] - med[b]:.1f} ms")


print("## Differences of medians (AWS minus localhost, same file)")
diff("lightsail-rust", "local-rust")
diff("agentcore-coordinator [new per call]", "local-coordinator [new per call]")
diff("agentcore-coordinator [reused]", "local-coordinator [reused]")

print()
print("## CLI checks (results/test-cli-all-*.txt)")
for f in sorted((RIG / "results").glob("test-cli-all-*.txt")):
    text = f.read_text()
    ok, bad = text.count("✅"), text.count("❌")
    endpoints = sum(1 for ln in text.splitlines() if ln.startswith("== "))
    print(f"{f.name}: {ok} of {ok + bad} checks passed across {endpoints} endpoints")
