# a2a-agentframework-azure

A sibling of [`a2a-strands-aws`](../a2a-strands-aws) and [`a2a-benchmark-rust`](../a2a-benchmark-rust) on Azure. The same Rust A2A v1.0 Mersenne prime agent runs in Azure Container Apps. A [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) coordinator on an Azure OpenAI model runs in Container Apps behind Entra ID. One client, the [A2A CLI](https://github.com/a2aproject/a2a-cli), drives all of them with the same commands, on localhost and on Azure.

| Agent | Where | A2A | How the CLI reaches it |
|---|---|---|---|
| `mersenne-agent` (Rust, `a2a-rs` SDK) | localhost:8304 | 1.0, JSON-RPC + REST | `a2a send -a http://localhost:8304 ...` |
| `mersenne-agent` (same image) | Container Apps, 0.25 vCPU / 0.5 GiB, 1 replica | 1.0, JSON-RPC + REST | `a2a send -a https://a2a-rust-mersenne.<env>.eastus2.azurecontainerapps.io ...` |
| Agent Framework coordinator (`coordinator/main.py`) | localhost:8309 | 1.0, JSON-RPC + REST | `a2a send -a http://localhost:8309 ...` |
| Agent Framework coordinator (same code) | Container Apps, Entra ID auth | 1.0, JSON-RPC + REST | `a2a --auth "Bearer <entra token>" send -a https://a2a-af-coordinator.<env>... ...` |

```
a2a CLI ──► Container Apps auth (Entra ID JWT) ──► Agent Framework Agent ──Entra ID──► Azure OpenAI gpt-5.4-mini
                                                         └── find_mersenne_primes tool
                                                               └── a2a-sdk 1.x client ──► Container Apps (A2A 1.0) ──► mersenne-agent
a2a CLI ──────────────────────────────────────────────────────────────────────────────► Container Apps (A2A 1.0)
```

Agent Framework's A2A package is built on `a2a-sdk` 1.x, so every hop is A2A 1.0. The coordinator's tool calls the Rust agent with the SDK's own client, sends a data part (`{"count": N}`) and reads the agent's structured report back. The CLI reads the coordinator's card the same way it reads the Rust agent's: `A2A v1.0`, with JSON-RPC and HTTP+JSON interfaces.

#### Versions

| Component | Version |
|---|---|
| A2A CLI (`a2a`) | v0.3.1 |
| `a2a-lf` / `a2a-server-lf` | 0.4.2 / 0.5.3 (A2A 1.0) |
| `agent-framework-core` / `agent-framework-openai` / `agent-framework-a2a` | 1.24.0 / 1.18.0 / 1.0.0b261030 |
| `a2a-sdk` / `azure-identity` | 1.3.0 / 1.27.0 |
| Model | `gpt-5.4-mini` (2026-03-17), Azure OpenAI GlobalStandard, 50K TPM |
| Python (coordinator) | 3.14 |
| Rust | 1.99.1, edition 2024 |
| Region | eastus2 |

---

#### Step 1 — Model and shared resources

```bash
az login
scripts/deploy-model.py     # resource group, ACR, managed identity, Container Apps env, AIServices + gpt-5.4-mini
```

Model access is Entra ID only. The script grants "Cognitive Services OpenAI User" on the account to you (for local runs through `az login`) and to the rig's user-assigned identity (for the container). The coordinator uses `DefaultAzureCredential` in both places and holds no key.

#### Step 2 — Run it locally

```bash
scripts/start-local.sh          # Rust agent :8304, Agent Framework coordinator :8309
a2a card get -a http://localhost:8309
a2a send -a http://localhost:8304 --data-part '{"count": 6}'
a2a send -a http://localhost:8309 "Find the first 9 Mersenne primes"
```

`RUST_AGENT_URL=https://... scripts/start-local.sh` points the local coordinator at another Rust agent, such as the Container Apps one.

🔎 Tip: Agent Framework's A2A package needs `a2a-sdk` 1.x and Strands needs 0.3, and both rigs share one Python. `start-local.sh` installs the coordinator's packages into `build/local-site` with `pip install --target` and starts it with `PYTHONPATH=build/local-site`, so the two SDK versions never meet.

#### Step 3 — Rust agent on Container Apps

```bash
scripts/deploy-rust.py          # docker build, push to ACR, container app with external ingress
scripts/test-cli.sh aca-rust
```

The app pulls from the registry with the rig's managed identity (AcrPull, no registry password). `ADVERTISE_URL` is the app's HTTPS URL, which the script computes from the environment's default domain before creating the app, so the card's interfaces point at Container Apps from the first revision.

#### Step 4 — Agent Framework coordinator on Container Apps

```bash
scripts/deploy-coordinator.py   # Entra ID app registration, image, container app, built-in auth
scripts/test-cli.sh aca-coordinator
```

Inbound auth is Container Apps built-in authentication with the Microsoft provider, set to return 401 for any request without a valid token, the card included. The app registration exposes `api://<app id>` with one delegated scope and pre-authorizes the Azure CLI, so your own `az login` gets a token with no consent prompt:

```bash
URL=$(scripts/azure_state.py get coordinator_url)
TOKEN=$(scripts/entra-token.py)     # az account get-access-token --resource api://<app id>
a2a --auth "Bearer $TOKEN" card get -a "$URL"
a2a --auth "Bearer $TOKEN" send -a "$URL" --stream "first 11 Mersenne primes"
a2a --auth "Bearer $TOKEN" send -a "$URL" --transport rest "Find the first 3 Mersenne primes"
```

Base URL, one header. The card sits at the standard `/.well-known/agent-card.json` path, and each call goes to a fresh A2A context with no session header.

🔎 Tip: the async `azure.identity` credential needs `aiohttp`, and nothing in the Agent Framework or `a2a-sdk` dependency tree pulls it in. In a clean `python:3.14-slim` image the credential fails with `ImportError: aiohttp package is not installed` (`results/dependencies-20261106.txt`). `coordinator/requirements.txt` pins it.

🔎 Tip: Agent Framework's OpenAI client streams a reply as text deltas and then sends one more update holding the whole text under the same message id (`results/responses-stream-updates-20261106.txt`). `A2AExecutor` appends every update to one artifact, so the finished task would hold one part per token followed by the full reply again. `WholeTextA2AExecutor` in `coordinator/main.py` lets that closing update replace the artifact instead. Streaming clients still see the deltas arrive, and the finished task holds the reply once, as a single text part. On `--stream`, the CLI prints one `[artifact]` line for the streamed deltas and one for the replacement.

#### Step 5 — Same checks everywhere

`scripts/test-cli.sh all` runs one set of checks against all four endpoints. For each Rust agent it checks the card (A2A v1.0), send, stream, REST and a data part. For each coordinator it checks the card (A2A v1.0), send, stream and REST; for the cloud coordinator it also checks that a request without a token gets 401. Every reply check greps for the agent's reply line `Found first N Mersenne primes`; the coordinator checks also require it once per reply, with no repeated copy. Transcript: `results/test-cli-all-20261106T162111Z.txt`, 19 of 19 passed.

The cloud coordinator's log (`results/aca-coordinator-log-20261106.txt`) covers that run. Its three cloud coordinator calls (N=7, 11 and 3) each appear there answered by the Container Apps Rust agent, for example `rust agent https://a2a-rust-mersenne.braveground-531dbad2.eastus2.azurecontainerapps.io: Found first 11 Mersenne primes in 0.0339ms.`

#### Step 6 — Timing through the CLI

`scripts/cli-bench.py` times one `a2a` process per call. Rounds are interleaved across targets, and every reply is checked. The table quotes medians from the JSON files.

| Target | Calls ok | Wall median | Compute median | File |
|---|---|---|---|---|
| Rust, localhost | 20/20 | 10.5 ms | 0.02268 ms | `cli-bench-20261106T154938Z.json` |
| Rust, Container Apps (HTTPS) | 20/20 | 164.2 ms | 0.02985 ms | `cli-bench-20261106T154938Z.json` |
| Agent Framework, localhost | 20/20 | 1836.0 ms | — | `cli-bench-20261106T162003Z.json` |
| Agent Framework, Container Apps | 20/20 | 1891.2 ms | — | `cli-bench-20261106T162003Z.json` |

Differences of medians, computed by `scripts/summarize-results.py` (`results/summary-20261106.txt`): the Container Apps Rust agent takes 153.7 ms more than the local one, and the Container Apps coordinator 55.2 ms more than the local one. The coordinator ranges overlap (local 1374.5–4833.5 ms, Container Apps 1581.2–4372.4 ms): the model call dominates, and where the coordinator runs moves the median by less than the call-to-call spread.

N=10 throughout. Wall time includes process start, card fetch, TLS on Azure and, for the coordinators, an Azure OpenAI call plus a nested A2A call to a Rust agent. The local coordinator calls the local Rust agent; the cloud coordinator calls the Container Apps one.

#### Compare and Contrast: AWS and Azure

| | `a2a-strands-aws` | `a2a-agentframework-azure` |
|---|---|---|
| Rust agent host | Lightsail container service, nano | Container Apps, 0.25 vCPU / 0.5 GiB |
| Coordinator framework | Strands (`a2a-sdk` 0.3, A2A 0.3) | Agent Framework (`a2a-sdk` 1.3, A2A 1.0) |
| Coordinator → Rust agent | `a2a` CLI inside the image | `a2a-sdk` 1.x client |
| Coordinator host | AgentCore Runtime, arm64, port 9000 | Container Apps, amd64, any port |
| Inbound auth | Cognito JWT, plus a 33+ character session id header | Entra ID JWT via built-in auth |
| Card URL for the CLI | full `.../invocations/.well-known/agent-card.json` | base URL |
| Model credentials | IAM role | managed identity, Entra ID |

#### Evidence

| File | What it holds |
|---|---|
| `results/test-cli-all-20261106T162111Z.txt` | the 19 checks |
| `results/cli-bench-20261106T154938Z.json`, `results/cli-bench-20261106T162003Z.json` | timing, per target |
| `results/summary-20261106.txt` | the figures above, from `scripts/summarize-results.py` |
| `results/aca-coordinator-log-20261106.txt` | the cloud coordinator's tool calls to the Rust agent during that check run |
| `results/cards-20261106.txt` | both Container Apps cards, full JSON |
| `results/sends-20261106.txt` | full CLI output for sample calls to both cloud agents, plus the 401s for no token and a malformed one |
| `results/entra-token-claims-20261106.txt` | audience, issuer, version, scope and client of the token `scripts/entra-token.py` returns (no token stored) |
| `results/responses-stream-updates-20261106.txt` | every text update of one streamed reply, ending in the whole-text repeat |
| `results/dependencies-20261106.txt` | `agent-framework-a2a` requiring `a2a-sdk` 1.x, the shared Python's 0.3, and the missing-`aiohttp` failure |
| `results/deploy-{model,rust,coordinator}-20261106.log` | every `az` command the deploy scripts ran |
| `results/env-20261106.txt` | tool and package versions, model, image tags, app sizes |

#### Teardown

```bash
make teardown   # app registration, then the resource group, then purge the soft-deleted AIServices account
```

#### Scope

One region (eastus2), one replica of each app at 0.25 vCPU, one model, N=10 for timing, twenty reps per target, on 2026-11-06. The timings show where the time goes; they are not a platform comparison at load.

#### Layout

```
src/lib.rs                   Lucas-Lehmer workload + Report (copy of ../a2a-strands-aws)
src/bin/mersenne-agent.rs    native A2A v1.0 agent (a2a-server-lf), default port 8304
coordinator/main.py          Agent Framework coordinator, A2A 1.0 server + a2a-sdk client tool
docker/                      agent and coordinator images (linux/amd64)
scripts/                     deploy (model, rust, coordinator), teardown, start/stop, test-cli, cli-bench, entra-token
results/                     test transcripts and timing JSON
```

#### References

- [Introducing the A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/)
- [a2aproject/a2a-cli](https://github.com/a2aproject/a2a-cli)
- [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs)
- [microsoft/agent-framework](https://github.com/microsoft/agent-framework)
- [Authentication in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication)
