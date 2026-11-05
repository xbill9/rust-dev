"""Strands coordinator for the Rust Mersenne prime agent.

A Strands ``Agent`` on a Bedrock model, served over A2A by the Bedrock
AgentCore SDK (``serve_a2a``): JSON-RPC at ``/``, the card at
``/.well-known/agent-card.json`` and ``/ping``. The same file runs locally
and inside AgentCore Runtime.

Strands' A2A stack is ``a2a-sdk`` 0.3 (protocol 0.3). The Rust agent speaks
protocol 1.0, whose card the 0.3 Python client cannot parse. The tool below
therefore calls the Rust agent with the ``a2a`` CLI, the same client the
scripts use from a laptop.

Env:
  RUST_AGENT_URL  Rust agent base URL (default http://localhost:8204)
  MODEL_ID        Bedrock model or inference profile (default us.anthropic.claude-haiku-5-5)
  A2A_PORT        listen port (default 9000, the AgentCore A2A contract)
  A2A_BIN         a2a CLI path (default: a2a on PATH)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from bedrock_agentcore.runtime import serve_a2a
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.multiagent.a2a.executor import StrandsA2AExecutor

RUST_AGENT_URL = os.environ.get("RUST_AGENT_URL", "http://localhost:8204").rstrip("/")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-5-5")
A2A_BIN = os.environ.get("A2A_BIN", "a2a")
MAX_N = 26  # length of the exponent table in src/lib.rs

log = logging.getLogger("coordinator")


@tool
def find_mersenne_primes(count: int) -> dict:
    """Find the first `count` Mersenne primes with the Rust A2A agent.

    The Rust agent runs the Lucas-Lehmer test and times itself. Quote the
    returned `summary` line exactly; do not recompute or round anything.

    Args:
      count: how many Mersenne primes to find, 1..26.

    Returns:
      dict with `summary` (the agent's own reply line), `requested`, `found`,
      `elapsed_ms`, `exponents` and the agent URL that answered.
    """
    count = int(count)
    if not 1 <= count <= MAX_N:
        return {"error": f"count must be 1..{MAX_N}, got {count}"}
    cmd = [
        A2A_BIN, "send", "-a", RUST_AGENT_URL, "-o", "json", "--timeout", "60s",
        "--data-part", json.dumps({"count": count}),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        return {"error": (proc.stderr or proc.stdout).strip()[-1500:]}
    task = json.loads(proc.stdout)["task"]
    summary, report = None, None
    for artifact in task.get("artifacts") or []:
        for part in artifact.get("parts", []):
            if "data" in part:
                report = part["data"]
            elif "text" in part:
                summary = part["text"]
    if report is None or summary is None:
        return {"error": f"no report in reply: {proc.stdout[:500]}"}
    # Data parts cross protobuf Struct, so integers can arrive as floats.
    found, requested = int(report["found"]), int(report["requested"])
    if requested != count or found != count:
        return {"error": f"asked for {count}, agent reports requested={requested} found={found}"}
    log.info("rust agent %s: %s", RUST_AGENT_URL, summary)
    return {
        "summary": summary,
        "requested": requested,
        "found": found,
        "elapsed_ms": report["elapsed_ms"],
        "exponents": [int(x) for x in report["exponents"]],
        "agent_url": RUST_AGENT_URL,
    }


SYSTEM_PROMPT = f"""
You coordinate a Rust A2A agent that finds the first N Mersenne primes (N <= {MAX_N}).

For any request to find, calculate or list Mersenne primes, call find_mersenne_primes
once with the N the user asked for (5 if they give none). Reply with the tool's
'summary' line exactly as returned, on its own first line, then the exponents.
Do not calculate, round or estimate anything yourself. If the tool returns an
error, report it.
"""


def create_agent(_context_id: str) -> Agent:
    return Agent(
        name="Strands Mersenne Coordinator",
        description=(
            "Strands agent on Amazon Bedrock that delegates Mersenne prime runs to a "
            "Rust A2A v1.0 agent through the a2a CLI."
        ),
        model=BedrockModel(model_id=MODEL_ID),
        system_prompt=SYSTEM_PROMPT,
        tools=[find_mersenne_primes],
        callback_handler=None,
    )


def agent_card() -> AgentCard:
    # `url` is a placeholder: serve_a2a replaces it with AGENTCORE_RUNTIME_URL
    # when set, else with http://localhost:$A2A_PORT/.
    return AgentCard(
        name="Strands Mersenne Coordinator",
        description=(
            "Strands agent on Amazon Bedrock (A2A 0.3) that delegates Mersenne prime "
            "runs to a Rust A2A 1.0 agent through the a2a CLI."
        ),
        url="http://localhost:9000/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="mersenne-via-rust",
                name="Mersenne primes via the Rust agent",
                description=f"Finds the first N Mersenne primes (N <= {MAX_N}) with the Rust A2A agent.",
                tags=["math", "rust", "strands", "bedrock"],
                examples=["Find the first 9 Mersenne primes"],
            )
        ],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("model %s, rust agent %s", MODEL_ID, RUST_AGENT_URL)
    port = int(os.environ.get("A2A_PORT", "9000"))
    # serve_a2a passes runtime_url=http://localhost:$port/, which overrides
    # the card's url; AGENTCORE_RUNTIME_URL wins over both.
    serve_a2a(StrandsA2AExecutor(agent_factory=create_agent), agent_card(), port=port)
