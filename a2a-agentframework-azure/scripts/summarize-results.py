#!/usr/bin/env python3
"""Print the figures the README quotes, computed from results/cli-bench-*.json.

  scripts/summarize-results.py > results/summary-20261106.txt

Wall times print to 0.1 ms, compute times to 4 significant figures. The
platform differences (Container Apps median minus localhost median, same
file) are computed here.
"""

import json
from pathlib import Path

RIG = Path(__file__).resolve().parents[1]
med = {}
for f in sorted((RIG / "results").glob("cli-bench-*.json")):
    d = json.loads(f.read_text())
    print(f"## {f.name}: N={d['n']}, {d['reps']} reps per target, {d['a2a']}")
    for name, t in d["targets"].items():
        w, c = t["wall_ms"], t["compute_ms"]
        line = (f"{name}: ok {t['ok']}/{t['calls']}, wall median {w['median']:.1f} ms "
                f"(min {w['min']:.1f}, max {w['max']:.1f})")
        if c:
            line += f", compute median {c['median']:.4g} ms (min {c['min']:.4g}, max {c['max']:.4g})"
        print(line)
        med[(f.name, name)] = w["median"]
    print()

print("## Differences of medians (Container Apps minus localhost, same file)")
for (fname, name), m in med.items():
    if name.startswith("aca-"):
        local = (fname, "local-" + name.removeprefix("aca-"))
        if local in med:
            print(f"{name} minus {local[1]}: {m - med[local]:.1f} ms")

print()
print("## CLI checks (results/test-cli-all-*.txt)")
for f in sorted((RIG / "results").glob("test-cli-all-*.txt")):
    text = f.read_text()
    ok, bad = text.count("✅"), text.count("❌")
    endpoints = sum(1 for ln in text.splitlines() if ln.startswith("== "))
    print(f"{f.name}: {ok} of {ok + bad} checks passed across {endpoints} endpoints")
