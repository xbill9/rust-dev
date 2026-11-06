---
title: "The A2A CLI on Azure: One Client for Container Apps, Agent Framework and Localhost"
published: false
description: "A Rust A2A v1.0 agent and a Microsoft Agent Framework A2A v1.0 coordinator on Azure Container Apps, behind Entra ID, driven by the same A2A CLI commands as their localhost copies."
tags: a2a, azure, rust, agents
cover_image: https://raw.githubusercontent.com/xbill9/rust-dev/main/a2a-agentframework-azure/docs/a2a-cli-azure/devto-cover.bbbb2d24.jpg
---

This article provides a step by step guide to running A2A agents on Azure and driving them with the A2A CLI. A Rust agent on the official A2A Rust SDK runs in Azure Container Apps. A Microsoft Agent Framework agent on an Azure OpenAI model runs in Container Apps behind Entra ID and hands its work to the Rust agent. Both also run on a laptop, and one set of `a2a` commands checks all four.

https://github.com/xbill9/rust-dev/tree/main/a2a-agentframework-azure

**The A2A CLI drove all four endpoints with the same commands, and 19 of 19 checks passed.** Every hop speaks A2A 1.0: the Rust SDK serves it, Agent Framework serves it, and the Agent Framework agent calls the Rust agent with the A2A 1.0 Python client. On Azure the CLI needs one extra flag, an Entra ID bearer token, which `az login` already provides. Model access, registry pulls and the token all run on Entra ID, with no API key anywhere.

---

#### What Is Being Built?

| Agent | Where it runs | A2A | Model |
| :--- | :--- | :--- | :--- |
| `mersenne-agent` (Rust) | laptop, port 8304 | 1.0, JSON-RPC and REST | none |
| `mersenne-agent` (same image) | Container Apps, 0.25 vCPU, 0.5 GiB | 1.0, JSON-RPC and REST | none |
| Agent Framework coordinator | laptop, port 8309 | 1.0, JSON-RPC and REST | `gpt-5.4-mini` on Azure OpenAI |
| Agent Framework coordinator (same code) | Container Apps, Entra ID auth | 1.0, JSON-RPC and REST | `gpt-5.4-mini` on Azure OpenAI |

```text
a2a CLI ──► Container Apps auth (Entra ID token) ──► Agent Framework Agent ──Entra ID──► Azure OpenAI gpt-5.4-mini
                                                           └── find_mersenne_primes tool
                                                                 └── a2a-sdk 1.x client ──► Container Apps (A2A 1.0) ──► mersenne-agent
a2a CLI ────────────────────────────────────────────────────────────────────────────────► Container Apps (A2A 1.0)
```

The workload is a Lucas-Lehmer test over the first N known Mersenne prime exponents, timed by the agent itself. Every reply carries the line `Found first N Mersenne primes in X ms.` and a data part with `requested`, `found` and `elapsed_ms`.

Versions, read from the machine on 2026-11-06:

| Component | Version |
| :--- | :--- |
| A2A CLI (`a2a`) | v0.3.1 |
| `a2a-lf` / `a2a-server-lf` (Rust SDK, A2A 1.0) | 0.4.2 / 0.5.3 |
| `agent-framework-core` / `agent-framework-openai` / `agent-framework-a2a` | 1.24.0 / 1.18.0 / 1.0.0b261030 |
| `a2a-sdk` (Python, A2A 1.0) / `azure-identity` | 1.3.0 / 1.27.0 |
| Python / Rust | 3.14.7 / 1.99.1 |
| Azure CLI | 2.90.0 |
| Model | `gpt-5.4-mini` 2026-03-17, GlobalStandard |
| Region | eastus2 |

---

#### At This Point You Should Have…

- The A2A CLI on your `PATH` as `a2a`: `go install github.com/a2aproject/a2a-cli@latest`, then rename `a2a-cli` to `a2a`
- Rust, Docker and Python 3
- The Azure CLI with the `containerapp` extension, signed in with `az login` to a subscription where you can create resource groups and Entra ID app registrations

```shell
a2a version
```

```text
a2a v0.3.1
```

---

#### Step 1 — The Model and the Shared Resources

```shell
git clone https://github.com/xbill9/rust-dev && cd rust-dev/a2a-agentframework-azure
scripts/deploy-model.py
```

The script creates one resource group in eastus2 holding a container registry, a user-assigned managed identity, a Container Apps environment and an AIServices account with a `gpt-5.4-mini` deployment. It grants "Cognitive Services OpenAI User" on the account twice: to the signed-in user, for the laptop, and to the managed identity, for the containers.

```text
$ az group create -n a2a-agentframework-azure-rg -l eastus2
$ az containerapp env create -n a2a-af-env -g a2a-agentframework-azure-rg -l eastus2 --logs-destination none
$ az cognitiveservices account create -n a2a-af-openai-defaba -g a2a-agentframework-azure-rg -l eastus2 --kind AIServices --sku S0 --custom-domain a2a-af-openai-defaba --yes
$ az cognitiveservices account deployment create ... --model-name gpt-5.4-mini --model-version 2026-03-17 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 50
✅ https://a2a-af-openai-defaba.cognitiveservices.azure.com/ deployment gpt-5.4-mini
```

The account gets a custom subdomain, and every call to the model authenticates with Entra ID. The coordinator holds no key.

---

#### Step 2 — Run Both Agents on the Laptop

```shell
scripts/start-local.sh
```

```text
up: 8304 rust agent, 8309 agent framework coordinator -> http://localhost:8304
```

The coordinator is an Agent Framework `Agent` with one tool, served over A2A 1.0 by `agent_framework_a2a` on the `a2a-sdk` server routes. The same file runs on the laptop and in Container Apps:

```python
client = OpenAIChatClient(
    model=MODEL,
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
agent = Agent(client=client, name=NAME, description=DESCRIPTION,
              instructions=INSTRUCTIONS, tools=[find_mersenne_primes])
handler = DefaultRequestHandler(
    agent_executor=WholeTextA2AExecutor(agent, stream=True),
    task_store=InMemoryTaskStore(),
    agent_card=card,
)
return Starlette(routes=[
    *create_agent_card_routes(card),
    *create_rest_routes(handler, path_prefix="/rest"),
    *create_jsonrpc_routes(handler, "/"),
])
```

`DefaultAzureCredential` picks up `az login` on the laptop and the managed identity in Azure. The CLI reads both cards and shows each one's protocol version:

```shell
a2a card get -a http://localhost:8304
a2a card get -a http://localhost:8309
```

```text
Name:         Mersenne Prime Agent Rust
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v1.0)     http://localhost:8304/jsonrpc
  HTTP+JSON (A2A v1.0)   http://localhost:8304/rest
Name:         Agent Framework Mersenne Coordinator
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v1.0)     http://localhost:8309/
  HTTP+JSON (A2A v1.0)   http://localhost:8309/rest
```

---

#### Step 3 — The Tool Calls the Rust Agent With the A2A 1.0 Python Client

Agent Framework's A2A package is built on `a2a-sdk` 1.x, the same protocol version as the Rust agent. The tool sends a data part and reads the Rust agent's structured report straight from the reply:

```python
value = Value()
value.struct_value.update({"count": count})
request = SendMessageRequest(message=Message(
    role=Role.ROLE_USER, message_id=os.urandom(16).hex(), parts=[Part(data=value)],
))
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
```

The tool refuses a reply whose `requested` or `found` differs from the count the model asked for, and the instructions tell the model to quote the agent's own reply line. The model picks N; the Rust agent does the counting and the timing. Data parts cross a protobuf `Struct`, so integers arrive as floats and the tool reads them with `int()`.

---

#### 🔎 Tip: Two A2A SDK Versions on One Python

`agent-framework-a2a` requires `a2a-sdk` 1.x, and the same machine runs a Strands rig whose `a2a-sdk` is pinned to 0.3:

```text
# agent-framework-a2a wheel metadata (Requires-Dist)
Requires-Dist: agent-framework-core>=1.22.0,<2
Requires-Dist: a2a-sdk>=1.0.0,<2

# shared pyenv Python (used by the Strands rig)
a2a-sdk 0.3.26
```

`scripts/start-local.sh` installs the coordinator's pinned requirements into `build/local-site` with `pip install --target`, and starts the coordinator with `PYTHONPATH=build/local-site`. The two SDK versions never meet, and the container image installs the same pins.

---

#### Step 4 — The Rust Agent on Container Apps

`scripts/deploy-rust.py` builds `docker/agent.Dockerfile`, pushes it to the registry and creates a container app with external ingress. The app pulls with the managed identity, which holds AcrPull, so there is no registry password. The script computes the app's address from the environment's default domain before creating it and sets `ADVERTISE_URL` to it, so the card points at Container Apps from the first revision.

```shell
scripts/deploy-rust.py
```

```text
$ docker build --platform linux/amd64 -f docker/agent.Dockerfile -t a2aafazuredefaba.azurecr.io/mersenne-agent:20261106T153734Z /home/xbill/rust-dev/a2a-agentframework-azure
$ docker push a2aafazuredefaba.azurecr.io/mersenne-agent:20261106T153734Z
$ az containerapp create -n a2a-rust-mersenne ... --target-port 8080 --ingress external --registry-identity <identity> --cpu 0.25 --memory 0.5Gi --min-replicas 1 --max-replicas 1 --env-vars PORT=8080 HOST=0.0.0.0 ADVERTISE_URL=https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io
✅ https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io/.well-known/agent-card.json
```

The commands are the laptop's, with the Container Apps address:

```shell
scripts/test-cli.sh aca-rust
```

```text
== aca-rust rust agent (https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io)
Interfaces:
  JSONRPC (A2A v1.0)     https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io/jsonrpc
  HTTP+JSON (A2A v1.0)   https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io/rest
✅ aca-rust card (A2A v1.0)
✅ aca-rust send
✅ aca-rust stream
✅ aca-rust rest
✅ aca-rust data-part
```

---

#### Step 5 — The Coordinator on Container Apps Behind Entra ID

`scripts/deploy-coordinator.py` does four things:

- creates an Entra ID app registration with the identifier URI `api://<app id>`, one delegated scope `access_as_user`, version 2 access tokens, and the Azure CLI's client id pre-authorized on that scope
- builds `docker/coordinator.Dockerfile` and pushes it
- creates the container app with `RUST_AGENT_URL` set to the Container Apps Rust agent and `AZURE_CLIENT_ID` set to the managed identity
- turns on Container Apps built-in authentication with the Microsoft provider, answering 401 to any request without a valid token

```shell
scripts/deploy-coordinator.py
```

```text
$ az containerapp auth microsoft update -n a2a-af-coordinator -g a2a-agentframework-azure-rg --client-id 67ce79d7-7432-4261-b394-d32c2fc36890 --issuer https://login.microsoftonline.com/<tenant>/v2.0 --allowed-audiences api://67ce79d7-7432-4261-b394-d32c2fc36890,67ce79d7-7432-4261-b394-d32c2fc36890 --yes
$ az containerapp auth update -n a2a-af-coordinator -g a2a-agentframework-azure-rg --enabled true --unauthenticated-client-action Return401
✅ https://a2a-af-coordinator.braveground-531dbad2.eastus2.azurecontainerapps.io/.well-known/agent-card.json (401 without a token)
```

From the CLI, the coordinator takes one flag beyond the laptop's: a bearer token for the app registration.

```shell
URL=$(scripts/azure_state.py get coordinator_url)
TOKEN=$(scripts/entra-token.py)    # az account get-access-token --resource api://<app id>
a2a --auth "Bearer $TOKEN" card get -a "$URL"
a2a --auth "Bearer $TOKEN" send -a "$URL" --transport rest "Find the first 3 Mersenne primes"
```

```text
Name:         Agent Framework Mersenne Coordinator
Interfaces:
  JSONRPC (A2A v1.0)     https://a2a-af-coordinator.braveground-531dbad2.eastus2.azurecontainerapps.io/
  HTTP+JSON (A2A v1.0)   https://a2a-af-coordinator.braveground-531dbad2.eastus2.azurecontainerapps.io/rest
Status:   completed (2026-11-06T16:20:22Z)
Artifacts:
  [msg_0a2ef6a5893a0e6d006aedfe460ca48195931f337d1ca8db4e] Found first 3 Mersenne primes in 0.0030ms.
2, 3, 5
```

The CLI takes the base URL, the card sits at the standard `/.well-known/agent-card.json` path, and each call gets its own A2A context with no session header. Without a token, and with a malformed one, the card itself answers 401:

```text
$ curl -s -o /dev/null -w '%{http_code}' $URL/.well-known/agent-card.json
401
$ curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer not-a-jwt' $URL/.well-known/agent-card.json
401
```

---

#### 🔎 Tip: Pre-Authorize the Azure CLI on the App Registration

With the Azure CLI's client id listed under `preAuthorizedApplications` for the `access_as_user` scope, `az account get-access-token --resource api://<app id>` returns a token for the coordinator with no consent prompt and no client secret. The token's claims, payload only:

```json
{
  "aud": "67ce79d7-7432-4261-b394-d32c2fc36890",
  "iss": "https://login.microsoftonline.com/40482c55-d00d-4c6d-8903-643d76a74b9c/v2.0",
  "ver": "2.0",
  "scp": "access_as_user",
  "azp": "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
}
```

`azp` is the Azure CLI. With `requestedAccessTokenVersion: 2` the audience is the bare app id and the issuer ends in `/v2.0`, so the built-in authentication lists both `api://<app id>` and `<app id>` as allowed audiences and uses the v2 issuer.

---

#### 🔎 Tip: Pin aiohttp for the Async Azure Credential

`azure.identity.aio` needs `aiohttp` for managed identity, and nothing in the Agent Framework or `a2a-sdk` dependency tree installs it. The same requirements without the pin, in a clean `python:3.14-slim-trixie` container:

```text
aiohttp dist-info dirs installed: 0
ImportError: aiohttp package is not installed
```

`coordinator/requirements.txt` pins `aiohttp==3.14.5`. A shared Python on a laptop that already has `aiohttp` from another package hides the gap, so the clean container is the place to check it.

---

#### Step 6 — One Reply, One Artifact

Agent Framework's OpenAI client streams a reply as text deltas, then sends one more update holding the whole text under the same message id. One streamed reply, every text update:

```text
1 msg_02d7537ef107 'Found'
2 msg_02d7537ef107 ' first'
...
21 msg_02d7537ef107 ' 7'
22 msg_02d7537ef107 'Found first 4 Mersenne primes in 0.0026ms.\n2, 3, 5, 7'
# last update repeats everything streamed before it under the same message_id: True
```

`A2AExecutor` appends every update to one artifact, which leaves the reply in the task twice. `WholeTextA2AExecutor` lets the closing update replace the artifact, so streaming clients see the deltas and the finished task holds the reply once, as a single text part:

```python
class WholeTextA2AExecutor(A2AExecutor):
    async def handle_events(self, item, updater, streamed_artifact_ids=None, default_artifact_id=None):
        if isinstance(item, AgentResponseUpdate):
            key = item.message_id or default_artifact_id or ""
            text = "".join(c.text for c in item.contents if c.type == "text" and c.text)
            so_far = self._streamed.get(key, "")
            if text and so_far and text == so_far:
                del self._streamed[key]
                if streamed_artifact_ids is not None:
                    streamed_artifact_ids.discard(key)  # next add_artifact replaces
            elif text:
                self._streamed[key] = so_far + text
        await super().handle_events(item, updater, streamed_artifact_ids, default_artifact_id)
```

```shell
a2a --auth "Bearer $TOKEN" send -a "$URL" -o json "Find the first 10 Mersenne primes"
```

```text
"artifacts": [
  {
    "artifactId": "msg_0df9fa92840724f8006aedfe47b9208195b7c9c1698118b7c1",
    "parts": [
      {
        "text": "Found first 10 Mersenne primes in 0.0549ms.\n2, 3, 5, 7, 13, 17, 19, 31, 61, 89"
      }
    ]
  }
]
```

The coordinator checks in the next step require the reply line exactly once, and the timing script counts a call only when it appears once.

---

#### Step 7 — The Same Checks on All Four Endpoints

`scripts/test-cli.sh all` starts the laptop agents and runs one set of checks against each endpoint. Each Rust agent gets card (A2A v1.0), send, stream, REST and a data part. Each coordinator gets card (A2A v1.0), send, stream and REST, and the Container Apps coordinator also gets a request with no token, which must answer 401.

```shell
scripts/test-cli.sh all
```

```text
== local rust agent (http://localhost:8304)
✅ local card (A2A v1.0)
✅ local send
✅ local stream
✅ local rest
✅ local data-part
== local agent framework coordinator (http://localhost:8309)
✅ local card (A2A v1.0)
✅ local send
✅ local stream
✅ local rest
== aca-rust rust agent (https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io)
✅ aca-rust card (A2A v1.0)
✅ aca-rust send
✅ aca-rust stream
✅ aca-rust rest
✅ aca-rust data-part
-- without a token (expect 401)
✅ aca-coordinator rejects no token (401)
== aca-coordinator agent framework coordinator (https://a2a-af-coordinator.braveground-531dbad2.eastus2.azurecontainerapps.io)
✅ aca-coordinator card (A2A v1.0)
✅ aca-coordinator send
✅ aca-coordinator stream
✅ aca-coordinator rest
```

The Container Apps coordinator checks ask for 7, 11 and 3 primes. All three reached the Container Apps Rust agent, and the coordinator's log shows each one:

```text
INFO:coordinator:rust agent https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io: Found first 7 Mersenne primes in 0.0059ms.
INFO:coordinator:rust agent https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io: Found first 11 Mersenne primes in 0.0339ms.
INFO:coordinator:rust agent https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io: Found first 3 Mersenne primes in 0.0039ms.
```

---

#### Step 8 — Timing the Same Command on Each Platform

`scripts/cli-bench.py` starts one `a2a` process per call and times it, so wall time includes starting the CLI, fetching the card, TLS on Azure and the reply. Targets take turns, one call each per round, so drift during the run lands on every target alike. Every reply is checked, and the statistics come from the script (`results/summary-20261106.txt`). N=10 and 20 calls per target throughout.

```shell
scripts/cli-bench.py --targets local-rust,aca-rust --reps 20 --n 10
```

```text
local-rust               ok 20/20  wall median 10.5 ms (min 7.9, max 12.3)  compute median 0.02268 ms
aca-rust                 ok 20/20  wall median 164.2 ms (min 143.4, max 199.9)  compute median 0.02985 ms
```

```shell
scripts/cli-bench.py --targets local-coordinator,aca-coordinator --reps 20 --n 10
```

```text
local-coordinator        ok 20/20  wall median 1836.0 ms (min 1374.5, max 4833.5)
aca-coordinator          ok 20/20  wall median 1891.2 ms (min 1581.2, max 4372.4)
```

The Rust agent's own compute time is a fraction of a millisecond on both machines, so the 153.7 ms between the laptop and Container Apps medians is the network and TLS. A coordinator call is an Azure OpenAI call plus a nested A2A call to a Rust agent. The Container Apps coordinator's median sits 55.2 ms above the laptop's, and both ranges span more than a second: the model call sets the time, and where the coordinator runs moves it by less than the spread between calls.

---

#### Step 9 — Teardown

```shell
make teardown
```

```text
$ az ad app delete --id 67ce79d7-7432-4261-b394-d32c2fc36890
$ az group delete -n a2a-agentframework-azure-rg --yes
$ az cognitiveservices account purge -n a2a-af-openai-defaba -g a2a-agentframework-azure-rg -l eastus2
deleted a2a-agentframework-azure-rg
```

Everything except the app registration lives in one resource group, so one delete removes it. The app registration lives in Entra ID and is deleted first. The script then purges the AIServices account, so no soft-deleted copy is left behind. Afterwards:

```text
$ az group exists -n a2a-agentframework-azure-rg
false
$ az cognitiveservices account list-deleted --query "[].name"
[]
```

`make deploy` recreates all three steps, and `make test-cli T=all` checks them again.

---

#### Compare and Contrast

| Endpoint | CLI flags beyond the laptop's | A2A | Median wall time, N=10 |
| :--- | :--- | :--- | ---: |
| Rust, laptop 🥇 | none | 1.0 | 10.5 ms |
| Rust, Container Apps 🥈 | none, HTTPS address | 1.0 | 164.2 ms |
| Agent Framework, laptop | none | 1.0 | 1836.0 ms |
| Agent Framework, Container Apps | `--auth` with an Entra ID token | 1.0 | 1891.2 ms |

---

#### So, Which One?

For an agent with no model in it, Container Apps is the short path: one container app with external ingress, a public HTTPS address and no client changes. Every call costs the network trip, 153.7 ms here, on top of a computation that takes a fraction of a millisecond.

For an agent built around a model, the same Container Apps environment hosts it behind Entra ID with built-in authentication and no code in the agent. The CLI adds one flag, and `az login` supplies the token. The model call sets the response time, wherever the agent runs.

For talking to any of them, the A2A CLI is the one client. With Agent Framework on A2A 1.0, the agents talk to each other with the Python SDK and the laptop talks to all of them with the CLI, over one protocol version end to end.

---

#### Summary

The goal of this article was to show that the A2A CLI drives the same agents on a laptop and on Azure Container Apps with the same commands. The key to the solution was A2A 1.0 on every hop, Entra ID for every credential, and one set of checks run against every endpoint. The results were:

- 🟢 19 of 19 CLI checks passed across four endpoints: card, send, stream, REST and data parts on the Rust agent; card, send, stream, REST and a 401 without a token on the coordinator
- 🟢 Agent Framework serves A2A 1.0 with JSON-RPC and REST, and its tool calls the Rust 1.0 agent with the `a2a-sdk` 1.x client
- 🟢 The Container Apps coordinator's calls reached the Container Apps Rust agent, confirmed in its log
- 🟢 No API keys and no registry password: Entra ID for the model, the image pull and the CLI's token
- ⚠️ The coordinator needs `WholeTextA2AExecutor`, or each reply lands in the task twice
- ⚠️ The async Azure credential needs `aiohttp` pinned; nothing else installs it
- ⚠️ Container Apps added 153.7 ms per Rust agent call over the laptop; the coordinators' medians differ by 55.2 ms, inside a spread of more than a second

Scope: one laptop (13th Gen Intel Core i7-1360P, Linux), one Azure region (eastus2), one replica of each app at 0.25 vCPU and 0.5 GiB, one model (`gpt-5.4-mini`), measured on 2026-11-06. Timing used N=10 with 20 calls per target, one run per comparison. Every Azure figure includes the trip from the laptop. Both apps kept one replica running, so cold starts were not measured; cost, gRPC, task commands, push notifications and load were not tested.

The strategy for running A2A agents on Azure and driving them with the A2A CLI was validated with an incremental step by step approach.

---

#### References

- The rig: https://github.com/xbill9/rust-dev/tree/main/a2a-agentframework-azure
- CLI check transcript: https://github.com/xbill9/rust-dev/blob/main/a2a-agentframework-azure/results/test-cli-all-20261106T162111Z.txt
- Timing summary: https://github.com/xbill9/rust-dev/blob/main/a2a-agentframework-azure/results/summary-20261106.txt
- A2A CLI: https://github.com/a2aproject/a2a-cli
- A2A Rust SDK: https://github.com/a2aproject/a2a-rs
- A2A Python SDK: https://github.com/a2aproject/a2a-python
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- Authentication and authorization in Azure Container Apps: https://learn.microsoft.com/azure/container-apps/authentication
- Managed identities in Azure Container Apps: https://learn.microsoft.com/azure/container-apps/managed-identity
- Configure Azure OpenAI with Microsoft Entra ID authentication: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/managed-identity
