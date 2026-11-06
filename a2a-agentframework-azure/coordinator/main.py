"""Microsoft Agent Framework coordinator for the Rust Mersenne prime agent.

An Agent Framework ``Agent`` on an Azure OpenAI model, served over A2A 1.0 by
``agent_framework_a2a.A2AExecutor`` on the ``a2a-sdk`` 1.x server: JSON-RPC
at ``/``, HTTP+JSON at ``/rest``, the card at
``/.well-known/agent-card.json``. The same file runs locally and in Azure
Container Apps.

Agent Framework's A2A stack is ``a2a-sdk`` 1.x (protocol 1.0), the same
protocol version as the Rust agent, so the tool calls the Rust agent with the
SDK's own client and reads its structured data part directly.

The model is reached with Entra ID (``DefaultAzureCredential``): your
``az login`` locally, the rig's user-assigned managed identity in the cloud
(``AZURE_CLIENT_ID``). No API key.

Env:
  RUST_AGENT_URL         Rust agent base URL (default http://localhost:8304)
  AZURE_OPENAI_ENDPOINT  https://<account>.cognitiveservices.azure.com/
  MODEL                  model deployment name (default gpt-5.4-mini)
  PORT                   listen port (default 8309)
  ADVERTISE_URL          public base URL for the card (default http://localhost:$PORT)
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

import httpx
import uvicorn
from a2a.client import ClientConfig, create_client
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes, create_rest_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Message, Part, Role,
    SendMessageRequest,
)
from agent_framework import Agent, tool
from agent_framework_a2a import A2AExecutor
from agent_framework_openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Value
from pydantic import Field
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

RUST_AGENT_URL = os.environ.get("RUST_AGENT_URL", "http://localhost:8304").rstrip("/")
MODEL = os.environ.get("MODEL", "gpt-5.4-mini")
PORT = int(os.environ.get("PORT", "8309"))
ADVERTISE_URL = os.environ.get("ADVERTISE_URL", f"http://localhost:{PORT}").rstrip("/")
MAX_N = 26  # length of the exponent table in src/lib.rs

log = logging.getLogger("coordinator")


@tool(approval_mode="never_require")
async def find_mersenne_primes(
    count: Annotated[int, Field(description="how many Mersenne primes to find, 1..26")],
) -> dict:
    """Find the first `count` Mersenne primes with the Rust A2A agent.

    The Rust agent runs the Lucas-Lehmer test and times itself. Quote the
    returned `summary` line exactly; do not recompute or round anything.
    Returns `summary` (the agent's own reply line), `requested`, `found`,
    `elapsed_ms`, `exponents` and the agent URL that answered.
    """
    count = int(count)
    if not 1 <= count <= MAX_N:
        return {"error": f"count must be 1..{MAX_N}, got {count}"}
    value = Value()
    value.struct_value.update({"count": count})
    request = SendMessageRequest(message=Message(
        role=Role.ROLE_USER, message_id=os.urandom(16).hex(), parts=[Part(data=value)],
    ))
    summary, report = None, None
    async with httpx.AsyncClient(timeout=60) as http:
        client = await create_client(
            RUST_AGENT_URL, ClientConfig(streaming=False, httpx_client=http))
        async for event in client.send_message(request):
            task = event.task if event.HasField("task") else None
            for artifact in (task.artifacts if task else []):
                for part in artifact.parts:
                    if part.HasField("data"):
                        report = MessageToDict(part.data)
                    elif part.HasField("text"):
                        summary = part.text
    if report is None or summary is None:
        return {"error": "no report in the Rust agent's reply"}
    # Data parts cross protobuf Struct: integers arrive as floats.
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


INSTRUCTIONS = f"""
You coordinate a Rust A2A agent that finds the first N Mersenne primes (N <= {MAX_N}).

For any request to find, calculate or list Mersenne primes, call find_mersenne_primes
once with the N the user asked for (5 if they give none). Reply with the tool's
'summary' line exactly as returned, on its own first line, then the exponents.
Do not calculate, round or estimate anything yourself. If the tool returns an
error, report it.
"""

NAME = "Agent Framework Mersenne Coordinator"
DESCRIPTION = (
    "Microsoft Agent Framework agent on Azure OpenAI (A2A 1.0) that delegates "
    "Mersenne prime runs to a Rust A2A 1.0 agent."
)


def agent_card() -> AgentCard:
    return AgentCard(
        name=NAME,
        description=DESCRIPTION,
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        supported_interfaces=[
            AgentInterface(url=f"{ADVERTISE_URL}/", protocol_binding="JSONRPC", protocol_version="1.0"),
            AgentInterface(url=f"{ADVERTISE_URL}/rest", protocol_binding="HTTP+JSON", protocol_version="1.0"),
        ],
        skills=[AgentSkill(
            id="mersenne-via-rust",
            name="Mersenne primes via the Rust agent",
            description=f"Finds the first N Mersenne primes (N <= {MAX_N}) with the Rust A2A agent.",
            tags=["math", "rust", "agent-framework", "azure-openai"],
            examples=["Find the first 9 Mersenne primes"],
        )],
    )


def app() -> Starlette:
    client = OpenAIChatClient(
        model=MODEL,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )
    agent = Agent(client=client, name=NAME, description=DESCRIPTION,
                  instructions=INSTRUCTIONS, tools=[find_mersenne_primes])
    card = agent_card()
    handler = DefaultRequestHandler(
        agent_executor=A2AExecutor(agent, stream=True),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(routes=[
        Route("/healthz", lambda _r: PlainTextResponse("ok")),
        *create_agent_card_routes(card),
        *create_rest_routes(handler, path_prefix="/rest"),
        *create_jsonrpc_routes(handler, "/"),
    ])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("model %s, rust agent %s, advertised at %s", MODEL, RUST_AGENT_URL, ADVERTISE_URL)
    uvicorn.run(app(), host="0.0.0.0", port=PORT)
