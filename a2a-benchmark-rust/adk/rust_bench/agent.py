"""ADK coordinator for the Rust Mersenne prime agents.

* Single calculations are delegated over A2A v1.0 to the two Rust agents
  (``RemoteA2aAgent``): the native SDK agent on :8104 and the
  ``a2a server --exec`` agent on :8105.
* Benchmarks go through the ``run_benchmark`` tool, which runs
  ``mersenne-bench`` and returns statistics computed in code. The model only
  quotes them: it never counts, sums or compares timings itself.

Run with the ADK CLI from the ``adk/`` directory:

  adk run rust_bench                      # interactive terminal
  adk web --port 8107                     # dev UI
  adk api_server --a2a --port 8106        # serve this agent over A2A
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

RIG = Path(__file__).resolve().parents[2]
BENCH = RIG / "target" / "release" / "mersenne-bench"
NATIVE_URL = os.getenv("NATIVE_URL", "http://localhost:8104")
EXEC_URL = os.getenv("EXEC_URL", "http://localhost:8105")
MAX_N = 26  # length of the exponent table in src/lib.rs

native_agent = RemoteA2aAgent(
    name="native_rust_agent",
    description=(
        "Rust A2A v1.0 agent on the official a2a-rs SDK. Finds the first N "
        "Mersenne primes (N <= 26) and reports the compute time."
    ),
    agent_card=f"{NATIVE_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

exec_agent = RemoteA2aAgent(
    name="exec_rust_agent",
    description=(
        "The same Rust Mersenne prime program, A2A-unaware, served by "
        "'a2a server --exec'. Finds the first N Mersenne primes (N <= 26)."
    ),
    agent_card=f"{EXEC_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)


def _sig4(x: float) -> float:
    return float(f"{x:.4g}")


def _summary(rows: list[dict], agent: str) -> dict:
    mine = [r for r in rows if r["agent"] == agent]
    if not mine:
        return {}
    over = [r["overhead_ms_median"] for r in mine]
    last = max(mine, key=lambda r: r["n"])
    return {
        "calls": sum(r["reps"] for r in mine),
        "overhead_ms_median_min": round(min(over), 3),
        "overhead_ms_median_max": round(max(over), 3),
        "largest_n": last["n"],
        "largest_n_found": last["found"],
        "largest_n_compute_ms_median": _sig4(last["compute_ms_median"]),
        "largest_n_rtt_ms_median": round(last["rtt_ms_median"], 3),
    }


def run_benchmark(min_n: int = 1, max_n: int = MAX_N, reps: int = 5) -> dict:
    """Benchmark both Rust agents for N = min_n..max_n, `reps` calls per N.

    Every call records the agent's own compute time and the client's round
    trip. All statistics are computed by the benchmark and this tool. Quote
    them exactly; do not recompute, round differently or estimate.

    Args:
      min_n: smallest N (>= 1).
      max_n: largest N (<= 26).
      reps: calls per N per agent (1..50).

    Returns:
      dict with the arguments actually used, a per-agent summary and the
      per-N rows (medians, minimums and maximums in milliseconds).
    """
    min_n = max(1, int(min_n))
    max_n = min(MAX_N, max(min_n, int(max_n)))
    reps = min(50, max(1, int(reps)))
    if not BENCH.exists():
        return {"error": f"{BENCH} missing: run 'cargo build --release' in {RIG}"}

    with tempfile.NamedTemporaryFile(suffix=".json") as out:
        proc = subprocess.run(
            [
                str(BENCH),
                "--min", str(min_n),
                "--max", str(max_n),
                "--reps", str(reps),
                "--out", out.name,
                "--agent", f"native={NATIVE_URL}",
                "--agent", f"exec={EXEC_URL}",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            return {"error": proc.stderr.strip()[-2000:]}
        rows = json.loads(Path(out.name).read_text())

    # Rounded here so the model has nothing left to round. Compute keeps 4
    # significant figures: fixed decimals would flatten sub-microsecond
    # medians toward 0. RTT and overhead keep 3 decimals (1 us).
    return {
        "used": {"min_n": min_n, "max_n": max_n, "reps": reps},
        "summary": {a: _summary(rows, a) for a in ("native", "exec")},
        "rows": [
            {
                "agent": r["agent"],
                "n": r["n"],
                "found": r["found"],
                "compute_ms_median": _sig4(r["compute_ms_median"]),
                "rtt_ms_median": round(r["rtt_ms_median"], 3),
                "overhead_ms_median": round(r["overhead_ms_median"], 3),
            }
            for r in rows
        ],
    }


root_agent = LlmAgent(
    name="rust_bench",
    model=os.getenv("MODEL_NAME", "gemini-3.8-flash"),
    description="Coordinator for the Rust Mersenne prime A2A agents.",
    instruction=f"""
You coordinate two Rust agents that find the first N Mersenne primes (N <= {MAX_N}).

- native_rust_agent: built on the official A2A Rust SDK.
- exec_rust_agent: the same Rust program wrapped by 'a2a server --exec'.

For one calculation ("find the first 12 Mersenne primes with the native agent"),
transfer to the named agent. If no agent is named, use native_rust_agent.
Their reply line reads "Found first N Mersenne primes in X.XXXXms."; pass it on as is.

For a benchmark or comparison, call run_benchmark once with the range and reps the
user asked for (defaults 1..{MAX_N}, 5 reps). Report the 'used' arguments and the numbers
from 'summary' and 'rows' exactly as returned. Do not calculate, average, round or
estimate anything yourself. If you need a figure the tool did not return, say so.
""",
    tools=[run_benchmark],
    sub_agents=[native_agent, exec_agent],
)
