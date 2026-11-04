#!/usr/bin/env python3
"""Wall time of `a2a send` (N=1) per transport, interleaved so drift hits all
cases alike. Usage: scripts/cli-transport.py [reps]  -> results/cli-transport-<stamp>.txt"""
import datetime, statistics, subprocess, sys, time
from pathlib import Path
reps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
cases = {
    "native, default (JSON-RPC)": ["a2a", "send", "-a", "http://localhost:8104", "-o", "json", "first 1"],
    "native, --transport rest": ["a2a", "send", "-a", "http://localhost:8104", "--transport", "rest", "-o", "json", "first 1"],
    "exec (HTTP+JSON only)": ["a2a", "send", "-a", "http://localhost:8105", "-o", "json", "first 1"],
    "a2a version": ["a2a", "version"],
}
ts = {k: [] for k in cases}
for _ in range(reps):
    for k, c in cases.items():
        t0 = time.perf_counter_ns(); subprocess.run(c, capture_output=True, check=True)
        ts[k].append((time.perf_counter_ns() - t0) / 1e6)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
lines = [f"# a2a send wall time by transport, N=1, {reps} reps each, interleaved ({stamp})"]
lines += [f"{k}: median {statistics.median(v):.2f} ms, min {min(v):.2f}, max {max(v):.2f}" for k, v in ts.items()]
out = Path(__file__).resolve().parents[1] / "results" / f"cli-transport-{stamp}.txt"
out.write_text("\n".join(lines) + "\n"); print("\n".join(lines))
