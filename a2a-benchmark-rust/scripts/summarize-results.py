#!/usr/bin/env python3
"""Aggregate figures the article quotes, computed from results/*.json.

Usage: scripts/summarize-results.py > results/summary-<date>.txt
"""
import json
import statistics
import sys
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "results"
SERIES = {
    "direct, 20 reps": "bench-20261103T211408Z.json",
    "ADK gemini-3.5-flash, 3 reps": "bench-20261103T211814Z.json",
    "ADK gemini-3.8-flash, 3 reps": "bench-20261103T213900Z.json",
}


def fmt(x):
    return f"{x:.2f}"


for label, name in SERIES.items():
    rows = json.loads((RES / name).read_text())
    print(f"== {label} ({name}): {len(rows)} rows")
    for agent in sorted({r["agent"] for r in rows}):
        mine = [r for r in rows if r["agent"] == agent]
        over = [r["overhead_ms_median"] for r in mine]
        ok = sum(r["found"] == min(r["n"], 26) for r in mine)
        print(f"{agent}: rows {len(mine)}, found==min(N,26) in {ok} of {len(mine)}")
        print(f"{agent}: per-N median overhead ms min {fmt(min(over))} max {fmt(max(over))} median {fmt(statistics.median(over))}")
        worst = max(mine, key=lambda r: r["rtt_ms_max"])
        print(f"{agent}: slowest single call {worst['rtt_ms_max'] / 1000:.1f} s at N={worst['n']}")
        if agent == "adk":
            routes = {tuple(r.get("routed_to", [])) for r in mine}
            srcs = {r.get("report_source") for r in mine}
            print(f"{agent}: routed_to {sorted(routes)} report_source {sorted(srcs)}")
        n26 = [r for r in mine if r["n"] == 26]
        if n26:
            print(f"{agent}: N=26 compute median ms {n26[0]['compute_ms_median']:.0f}")

for name, gap in (("gap-20261103-native-0ms.json", 0), ("gap-20261103-native-1300ms.json", 1300)):
    rows = json.loads((RES / name).read_text())
    print(f"== {name}: idle gap before each call {gap / 1000:.1f} s")
    for r in rows:
        print(f"N={r['n']} compute median ms {fmt(r['compute_ms_median'])}")
    sys.stdout.flush()
