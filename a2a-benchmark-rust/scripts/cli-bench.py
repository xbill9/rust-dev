#!/usr/bin/env python3
"""Time the A2A CLI itself as a client: one `a2a send -o json` process per call.

Usage: scripts/cli-bench.py [--min 1] [--max 26] [--reps 5] [--adk-reps 3] [--no-adk]

Each call records the wall time of the whole `a2a send` process (start, card
fetch, send, exit) and the agent's own compute time from its report. The
report must answer the question asked (requested == N, found == min(N, 26));
through ADK the history must show a transfer_to_agent, so the timing comes
from a Rust agent. Two reference timings separate the CLI's own cost:
`a2a version` (process start, no network) and `a2a card get` (start + one
card fetch). All statistics are computed here.

Writes results/cli-bench-<stamp>.json and .md.
"""
import argparse
import datetime
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

RIG = Path(__file__).resolve().parents[1]
TABLE_LEN = 26
AGENTS = {
    "native": "http://localhost:8104",
    "exec": "http://localhost:8105",
    "adk": "http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json",
}


def timed(cmd, timeout=300):
    t0 = time.perf_counter_ns()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    ms = (time.perf_counter_ns() - t0) / 1e6
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: exit {p.returncode}: {p.stderr.strip()[-400:]}")
    return ms, p.stdout


def scan(v, reports, transfers):
    """Collect report objects (data parts or JSON lines in text) and transfers."""
    if isinstance(v, dict):
        if "elapsed_ms" in v and "found" in v:
            reports.append(v)
        if v.get("name") == "transfer_to_agent" and "args" in v:
            transfers.append(v["args"].get("agent_name"))
        for x in v.values():
            scan(x, reports, transfers)
    elif isinstance(v, list):
        for x in v:
            scan(x, reports, transfers)
    elif isinstance(v, str):
        for line in v.splitlines():
            line = line.strip()
            if line.startswith("{") and "elapsed_ms" in line:
                end = line.rfind("}")
                try:
                    reports.append(json.loads(line[: end + 1]))
                except json.JSONDecodeError:
                    pass


def checked(stdout, n, agent):
    task = json.loads(stdout)["task"]
    reports, transfers = [], []
    scan(task, reports, transfers)
    if agent == "adk" and not transfers:
        raise RuntimeError(f"N={n}: ADK reply has no transfer_to_agent")
    want = min(n, TABLE_LEN)
    good = [r for r in reports if r.get("requested") is not None and int(r["requested"]) == n and int(r["found"]) == want]
    if not good:
        raise RuntimeError(f"N={n} {agent}: no report answering requested={n} found={want}: {reports[:2]}")
    return float(good[0]["elapsed_ms"]), transfers


def stats(xs):
    return {"median": statistics.median(xs), "min": min(xs), "max": max(xs)}


def sig4(x):
    return f"{x:.4g}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=1)
    ap.add_argument("--max", type=int, default=TABLE_LEN)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--adk-reps", type=int, default=3)
    ap.add_argument("--no-adk", action="store_true")
    a = ap.parse_args()

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"stamp": stamp, "a2a_version": timed(["a2a", "version"])[1].splitlines()[0],
           "reference": {}, "rows": []}

    for name, cmd in {
        "a2a version": ["a2a", "version"],
        "a2a card get native": ["a2a", "card", "get", "-a", AGENTS["native"]],
        "a2a card get exec": ["a2a", "card", "get", "-a", AGENTS["exec"]],
    }.items():
        xs = [timed(cmd)[0] for _ in range(20)]
        out["reference"][name] = {"reps": 20, **stats(xs)}
        print(f"{name}: median {out['reference'][name]['median']:.2f} ms", file=sys.stderr)

    agents = ["native", "exec"] + ([] if a.no_adk else ["adk"])
    for agent in agents:
        reps = a.adk_reps if agent == "adk" else a.reps
        for n in range(a.min, a.max + 1):
            wall, comp, routes = [], [], set()
            for _ in range(reps):
                ms, so = timed(["a2a", "send", "-a", AGENTS[agent], "-o", "json", "--timeout", "300s",
                                f"Calculate the first {n} Mersenne primes"])
                c, tr = checked(so, n, agent)
                wall.append(ms)
                comp.append(c)
                routes.update(t for t in tr if t)
            over = [w - c for w, c in zip(wall, comp)]
            row = {"agent": agent, "n": n, "reps": reps, "found": min(n, TABLE_LEN),
                   "wall_ms": stats(wall), "compute_ms": stats(comp),
                   "overhead_ms": stats(over), "routed_to": sorted(routes)}
            out["rows"].append(row)
            print(f"{agent} N={n}: wall {row['wall_ms']['median']:.2f} ms, compute {sig4(row['compute_ms']['median'])} ms",
                  file=sys.stderr)

    summary = {}
    for agent in agents:
        mine = [r for r in out["rows"] if r["agent"] == agent]
        med = [r["overhead_ms"]["median"] for r in mine]
        summary[agent] = {"rows": len(mine), "calls": sum(r["reps"] for r in mine),
                          "overhead_ms_median_min": min(med), "overhead_ms_median_max": max(med),
                          "overhead_ms_median_of_medians": statistics.median(med),
                          "slowest_call_ms": max(r["wall_ms"]["max"] for r in mine),
                          "routed_to": sorted({x for r in mine for x in r["routed_to"]})}
    out["summary"] = summary

    res = RIG / "results"
    (res / f"cli-bench-{stamp}.json").write_text(json.dumps(out, indent=1))
    lines = [f"# a2a CLI as client ({stamp}, {out['a2a_version']})", "",
             "| reference | reps | median ms | min ms | max ms |", "|---|---:|---:|---:|---:|"]
    for k, v in out["reference"].items():
        lines.append(f"| `{k}` | {v['reps']} | {v['median']:.2f} | {v['min']:.2f} | {v['max']:.2f} |")
    lines += ["", "| agent | N | reps | wall ms | compute ms | overhead ms |", "|---|---:|---:|---:|---:|---:|"]
    for r in out["rows"]:
        lines.append(f"| {r['agent']} | {r['n']} | {r['reps']} | {r['wall_ms']['median']:.2f} | "
                     f"{sig4(r['compute_ms']['median'])} | {r['overhead_ms']['median']:.2f} |")
    lines += ["", "| agent | calls | overhead median min ms | max ms | median of medians ms | slowest call ms | routed to |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for k, s in summary.items():
        lines.append(f"| {k} | {s['calls']} | {s['overhead_ms_median_min']:.2f} | {s['overhead_ms_median_max']:.2f} | "
                     f"{s['overhead_ms_median_of_medians']:.2f} | {s['slowest_call_ms']:.1f} | {', '.join(s['routed_to'])} |")
    (res / f"cli-bench-{stamp}.md").write_text("\n".join(lines) + "\n")
    print(f"wrote results/cli-bench-{stamp}.json and .md", file=sys.stderr)


if __name__ == "__main__":
    main()
