# a2a-strands-aws

A sibling of [`a2a-benchmark-rust`](../a2a-benchmark-rust) on AWS. The same Rust A2A v1.0 Mersenne prime agent runs in a Lightsail container. A [Strands](https://strandsagents.com/) coordinator on an Amazon Bedrock model runs in Bedrock AgentCore Runtime. One client, the [A2A CLI](https://github.com/a2aproject/a2a-cli), drives all of them with the same commands, on localhost and on AWS.

| Agent | Where | A2A | How the CLI reaches it |
|---|---|---|---|
| `mersenne-agent` (Rust, `a2a-rs` SDK) | localhost:8204 | 1.0, JSON-RPC + REST | `a2a send -a http://localhost:8204 ...` |
| `mersenne-agent` (same image) | Lightsail container service, nano | 1.0, JSON-RPC + REST | `a2a send -a https://<service>.cs.amazonlightsail.com ...` |
| Strands coordinator (`coordinator/main.py`) | localhost:8209 | 0.3, JSON-RPC | `a2a send -a http://localhost:8209 ...` |
| Strands coordinator (same code, arm64 image) | Bedrock AgentCore Runtime | 0.3, JSON-RPC | `a2a --auth "Bearer <cognito token>" send -a <runtime card URL> ...` |

```
a2a CLI ──► AgentCore Runtime (A2A 0.3, Cognito JWT) ──► Strands Agent ──Bedrock──► Claude Haiku 5.5
                                                              └── find_mersenne_primes tool
                                                                    └── a2a CLI ──► Lightsail (A2A 1.0) ──► mersenne-agent
a2a CLI ──────────────────────────────────────────────────────────────────────────► Lightsail (A2A 1.0)
```

The coordinator's tool calls the Rust agent with the A2A CLI too. Strands uses `a2a-sdk` 0.3, whose card parser requires the top-level `url` field that A2A 1.0 cards replace with `supportedInterfaces`. The CLI reads both card versions, so the same Go binary that runs on the laptop also ships inside the AgentCore image.

#### Versions

| Component | Version |
|---|---|
| A2A CLI (`a2a`) | v0.3.1 (laptop; cross-compiled linux/arm64 in the coordinator image) |
| `a2a-lf` / `a2a-server-lf` | 0.4.2 / 0.5.3 (A2A 1.0) |
| `strands-agents` / `a2a-sdk` / `bedrock-agentcore` | 1.64.0 / 0.3.26 / 1.25.3 |
| Model | `us.anthropic.claude-haiku-5-5` on Bedrock (`MODEL_ID` overrides) |
| Rust | 1.99.1, edition 2024 |
| Region | us-east-1 |

---

#### Step 1 — Run it locally

```bash
scripts/start-local.sh          # Rust agent :8204, Strands coordinator :8209
a2a card get -a http://localhost:8204
a2a send -a http://localhost:8204 --data-part '{"count": 6}'
a2a send -a http://localhost:8209 "Find the first 9 Mersenne primes"
```

The coordinator uses Bedrock through your local AWS credentials. `RUST_AGENT_URL=https://... scripts/start-local.sh` points the local coordinator at another Rust agent, such as the Lightsail one.

#### Step 2 — Rust agent on Lightsail

```bash
scripts/deploy-lightsail.py     # nano service, builds docker/agent.Dockerfile, pushes, deploys
scripts/test-cli.sh lightsail
```

The service gets a public HTTPS URL. The container's `ADVERTISE_URL` is set to that URL, so the card's interfaces point at Lightsail. The health check is the agent card path.

#### Step 3 — Strands coordinator on AgentCore Runtime

```bash
scripts/deploy-agentcore.py     # ECR, IAM role, Cognito pool + user, runtime (A2A, CUSTOM_JWT)
scripts/test-cli.sh agentcore
```

AgentCore runs arm64 containers on port 9000, with the card at `/.well-known/agent-card.json` and `/ping`. `bedrock_agentcore.runtime.serve_a2a` provides all of that. `scripts/build-coordinator.sh` builds the arm64 image on an x86 machine with no emulator: pip downloads aarch64 wheels (`--platform manylinux_2_28_aarch64`), Go cross-compiles the CLI, and the Dockerfile only copies. `ARCH=amd64` builds the same image for a local smoke test.

Calling it from the CLI takes two flags and the full card URL:

```bash
CARD=$(scripts/aws_state.py get agentcore_card)    # https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<escaped ARN>/invocations/.well-known/agent-card.json
TOKEN=$(scripts/cognito-token.py)
SID="a2a-cli-$(cat /proc/sys/kernel/random/uuid)"  # session ids are 33+ characters
a2a --auth "Bearer $TOKEN" --svc-param "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=$SID" card get -a "$CARD"
a2a --auth "Bearer $TOKEN" --svc-param "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=$SID" send -a "$CARD" --stream "first 11 Mersenne primes"
```

🔎 Tip: pass the card URL, not the `.../invocations/` URL. Given a URL without a card path, the CLI asks the origin `https://bedrock-agentcore.us-east-1.amazonaws.com/.well-known/agent-card.json` and gets a 404.

#### Step 4 — Same checks everywhere

`scripts/test-cli.sh all` runs one set of checks against all four endpoints. For each Rust agent it checks the card (A2A v1.0), send, stream, REST and a data part. For each coordinator it checks the card (A2A v0.3), send and stream. Every check greps for the agent's reply line `Found first N Mersenne primes`. Transcript: `results/test-cli-all-20261105T163653Z.txt`, 16 of 16 passed.

The Lightsail agent's log confirms the AgentCore hop: the `requested=7` and `requested=11` runs from the AgentCore checks appear there.

#### Step 5 — Timing through the CLI

`scripts/cli-bench.py` times one `a2a` process per call. Rounds are interleaved across targets, and every reply is checked. The table quotes medians from the JSON files.

| Target | Calls ok | Wall median | Compute median | File |
|---|---|---|---|---|
| Rust, localhost | 20/20 | 27.7 ms | 0.05682 ms | `cli-bench-20261105T163732Z.json` |
| Rust, Lightsail (HTTPS) | 20/20 | 154.4 ms | 0.03928 ms | `cli-bench-20261105T163732Z.json` |
| Strands, localhost | 5/5 | 2596.2 ms | — | `cli-bench-20261105T164025Z.json` |
| Strands, AgentCore, new session per call | 5/5 | 3416.5 ms | — | `cli-bench-20261105T164025Z.json` |
| Strands, AgentCore, one session | 5/5 | 2997.1 ms | — | `cli-bench-20261105T163943Z.json` |

N=10 throughout. Wall time includes process start, card fetch, TLS on AWS and, for the coordinators, a Bedrock model call plus a nested CLI call to the Rust agent. In the one-session run the first AgentCore call took 12177.7 ms (the file's max) and the rest stayed near the median.

#### Teardown

```bash
make teardown   # deploy-agentcore.py --delete, then deploy-lightsail.py --delete
```

#### Scope

One region (us-east-1), one Lightsail power (nano), one model, N=10 for timing, five or twenty reps per target, on 2026-11-05. The timings show where the time goes; they are not a platform comparison at load.
