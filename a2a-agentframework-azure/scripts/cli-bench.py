#!/usr/bin/env python3
"""Time the a2a CLI against every platform with the same command.

Rounds are interleaved (one call per target per round), so drift over the run
hits every target alike. Each call is one `a2a` process: wall time covers
process start, card fetch, TLS where there is TLS, and the reply. Rust
targets also return their own Lucas-Lehmer compute time (`elapsed_ms`).
Every reply is checked: requested == found == N for the Rust agent, the
reply line "Found first N Mersenne primes" for a coordinator. Statistics are
computed here; quote the JSON, not a hand calculation.

  scripts/cli-bench.py --targets local-rust,aca-rust --reps 20 --n 10
  scripts/cli-bench.py --targets local-coordinator,aca-coordinator --reps 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import load  # noqa: E402

RIG = Path(__file__).resolve().parents[1]


def targets() -> dict[str, dict]:
    s = load()
    t = {
        "local-rust": {"url": "http://localhost:8304", "kind": "rust", "platform": "local"},
        "local-coordinator": {"url": "http://localhost:8309", "kind": "coordinator", "platform": "local"},
    }
    if "rust_url" in s:
        t["aca-rust"] = {"url": s["rust_url"], "kind": "rust", "platform": "container-apps"}
    if "coordinator_url" in s:
        t["aca-coordinator"] = {"url": s["coordinator_url"], "kind": "coordinator",
                                "platform": "container-apps", "auth": True}
    return t


def token() -> str:
    return subprocess.run([sys.executable, str(RIG / "scripts/entra-token.py")], check=True,
                          capture_output=True, text=True).stdout.strip()


def call(t: dict, n: int, tok: str | None) -> dict:
    cmd = ["a2a"]
    if t.get("auth"):
        cmd += ["--auth", f"Bearer {tok}"]
    cmd += ["--timeout", "120s", "send", "-a", t["url"], "-o", "json"]
    cmd += ["--data-part", json.dumps({"count": n})] if t["kind"] == "rust" else [f"Find the first {n} Mersenne primes"]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    wall_ms = (time.perf_counter() - t0) * 1000
    row = {"wall_ms": wall_ms, "ok": False}
    if p.returncode != 0:
        row["error"] = (p.stderr or p.stdout)[-300:]
        return row
    out = json.loads(p.stdout)
    task = out.get("task") or out
    if t["kind"] == "rust":
        data = next(pt["data"] for a in task["artifacts"] for pt in a["parts"] if "data" in pt)
        row["compute_ms"] = data["elapsed_ms"]
        row["ok"] = int(data["requested"]) == n and int(data["found"]) == n
    else:
        text = " ".join(pt.get("text", "") for a in task.get("artifacts") or [] for pt in a["parts"])
        row["ok"] = f"Found first {n} Mersenne primes" in text
        if not row["ok"]:
            row["error"] = text[:300]
    return row


def stats(xs: list[float]) -> dict:
    return {"median": statistics.median(xs), "min": min(xs), "max": max(xs)} if xs else {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="local-rust,aca-rust")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out")
    a = ap.parse_args()
    known = targets()
    names = a.targets.split(",")
    missing = [x for x in names if x not in known]
    if missing:
        sys.exit(f"unknown or undeployed targets {missing}; known: {list(known)}")
    tok = token() if any(known[x].get("auth") for x in names) else None
    rows: dict[str, list[dict]] = {x: [] for x in names}
    call(known[names[0]], a.n, tok)  # warm-up, discarded
    for r in range(a.reps):
        for x in names:
            rows[x].append(call(known[x], a.n, tok))
        print(f"round {r + 1}/{a.reps}", file=sys.stderr, flush=True)
    result = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n": a.n, "reps": a.reps, "a2a": subprocess.run(["a2a", "version"], capture_output=True,
                                                        text=True).stdout.split("\n")[0],
        "targets": {},
    }
    for x in names:
        good = [r for r in rows[x] if r["ok"]]
        result["targets"][x] = {
            **{k: v for k, v in known[x].items() if k != "auth"},
            "calls": len(rows[x]), "ok": len(good),
            "errors": [r.get("error") for r in rows[x] if not r["ok"]][:3],
            "wall_ms": stats([r["wall_ms"] for r in good]),
            "compute_ms": stats([r["compute_ms"] for r in good if "compute_ms" in r]),
        }
    out = Path(a.out) if a.out else RIG / "results" / f"cli-bench-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    for x, v in result["targets"].items():
        w, c = v["wall_ms"], v["compute_ms"]
        line = f"{x:24} ok {v['ok']}/{v['calls']}"
        if w:
            line += f"  wall median {w['median']:.1f} ms (min {w['min']:.1f}, max {w['max']:.1f})"
        if c:
            line += f"  compute median {c['median']:.4g} ms"
        print(line)
    print(f"wrote {out.relative_to(RIG)}")


if __name__ == "__main__":
    main()
