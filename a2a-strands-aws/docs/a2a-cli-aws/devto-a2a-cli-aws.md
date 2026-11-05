---
title: "The A2A CLI on AWS: One Client for Lightsail, Bedrock AgentCore and Localhost"
published: false
description: "A Rust A2A v1.0 agent on Amazon Lightsail and a Strands A2A v0.3 coordinator on Bedrock AgentCore Runtime, driven by the same A2A CLI commands as their localhost copies, with the CLI also carrying the agent-to-agent call between them."
tags: a2a, aws, rust, agents
cover_image: https://raw.githubusercontent.com/xbill9/rust-dev/main/a2a-strands-aws/docs/a2a-cli-aws/devto-cover.69a65719.jpg
---

This article provides a step by step guide to running A2A agents on AWS and driving them with the A2A CLI. A Rust agent on the official A2A Rust SDK runs in an Amazon Lightsail container. A Strands agent on an Amazon Bedrock model runs in Amazon Bedrock AgentCore Runtime and hands its work to the Rust agent. Both also run on a laptop, and one set of `a2a` commands checks all four.

https://github.com/xbill9/rust-dev/tree/main/a2a-strands-aws

**The A2A CLI drove all four endpoints with the same commands, 16 of 16 checks passed, and the CLI also carried the call from the Strands agent to the Rust agent.** The two agents speak different protocol versions: the Rust SDK serves A2A 1.0 and Strands serves A2A 0.3. The CLI reads both. Strands' own Python client reads only 0.3, so the Strands agent calls the Rust agent by running the same `a2a` binary the laptop uses. On AWS the CLI needs a login token, a session header and the full agent card URL, and nothing else changes.

---

#### What Is Being Built?

| Agent | Where it runs | A2A | Model |
| :--- | :--- | :--- | :--- |
| `mersenne-agent` (Rust) | laptop, port 8204 | 1.0, JSON-RPC and REST | none |
| `mersenne-agent` (same image) | Lightsail container service, nano | 1.0, JSON-RPC and REST | none |
| Strands coordinator | laptop, port 8209 | 0.3, JSON-RPC | Claude Haiku 5.5 on Bedrock |
| Strands coordinator (same code) | Bedrock AgentCore Runtime | 0.3, JSON-RPC | Claude Haiku 5.5 on Bedrock |

```text
a2a CLI ──► AgentCore Runtime (A2A 0.3, Cognito token) ──► Strands Agent ──Bedrock──► Claude Haiku 5.5
                                                                └── find_mersenne_primes tool
                                                                      └── a2a CLI ──► Lightsail (A2A 1.0) ──► mersenne-agent
a2a CLI ──────────────────────────────────────────────────────────────────────────► Lightsail (A2A 1.0)
```

The workload is the one from the sibling rig: a Lucas-Lehmer test over the first N known Mersenne prime exponents, timed by the agent itself. Every reply carries the line `Found first N Mersenne primes in X ms.` and a data part with `requested`, `found` and `elapsed_ms`.

Versions, read from the machine on 2026-11-05:

| Component | Version |
| :--- | :--- |
| A2A CLI (`a2a`) | v0.3.1 |
| `a2a-lf` / `a2a-server-lf` (Rust SDK, A2A 1.0) | 0.4.2 / 0.5.3 |
| `strands-agents` / `a2a-sdk` / `bedrock-agentcore` | 1.64.0 / 0.3.26 / 1.25.3 |
| Rust | 1.99.1, edition 2024 |
| Model | `us.anthropic.claude-haiku-5-5` on Bedrock |
| Region | us-east-1 |

---

#### At This Point You Should Have…

- The A2A CLI on your `PATH` as `a2a`: `go install github.com/a2aproject/a2a-cli@latest`, then rename `a2a-cli` to `a2a`
- Rust, Go, Docker and Python 3 with `pip install "strands-agents[a2a]" "bedrock-agentcore[a2a]"`
- AWS credentials with Bedrock model access in us-east-1, and the `lightsailctl` plugin for the AWS CLI

```shell
a2a version
```

```text
a2a v0.3.1
commit:  none
built:   unknown
go:      go1.26.3
os/arch: linux/amd64
```

---

#### Step 1 — Run Both Agents on the Laptop

```shell
git clone https://github.com/xbill9/rust-dev && cd rust-dev/a2a-strands-aws
scripts/start-local.sh
```

```text
up: 8204 rust agent, 8209 strands coordinator -> http://localhost:8204
```

The coordinator is a Strands `Agent` with one tool, served over A2A by the AgentCore SDK's `serve_a2a`. The same file runs on the laptop and in AgentCore:

```python
def create_agent(_context_id: str) -> Agent:
    return Agent(
        name="Strands Mersenne Coordinator",
        model=BedrockModel(model_id=MODEL_ID),
        system_prompt=SYSTEM_PROMPT,
        tools=[find_mersenne_primes],
        callback_handler=None,
    )

serve_a2a(StrandsA2AExecutor(agent_factory=create_agent), agent_card(), port=port)
```

The CLI reads both cards and shows each one's protocol version:

```shell
a2a card get -a http://localhost:8204
a2a card get -a http://localhost:8209
```

```text
Name:         Mersenne Prime Agent Rust
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v1.0)     http://localhost:8204/jsonrpc
  HTTP+JSON (A2A v1.0)   http://localhost:8204/rest
Name:         Strands Mersenne Coordinator
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v0.3.0)   http://localhost:8209/
Streaming:    true
```

---

#### Step 2 — Why the Strands Tool Calls the A2A CLI

Strands pins `a2a-sdk` below 0.4, so its A2A client and server speak protocol 0.3. An A2A 1.0 card lists its endpoints under `supportedInterfaces` and drops the top-level `url` field that a 0.3 card requires. `scripts/check-sdk03-card.py` fetches each card with the 0.3 client:

```shell
scripts/check-sdk03-card.py http://localhost:8204
scripts/check-sdk03-card.py http://localhost:8209
```

```text
a2a-sdk 0.3.26, card from http://localhost:8204
A2AClientJSONError: JSON Error: Failed to validate agent card structure from http://localhost:8204/.well-known/agent-card.json: [{"type":"missing","loc":["url"],"msg":"Field required", ...
a2a-sdk 0.3.26, card from http://localhost:8209
ok: Strands Mersenne Coordinator, protocolVersion 0.3.0, url http://localhost:8209/
```

The A2A CLI reads both, so the tool runs it with JSON output and a data part, then reads the Rust agent's structured report:

```python
cmd = [
    A2A_BIN, "send", "-a", RUST_AGENT_URL, "-o", "json", "--timeout", "60s",
    "--data-part", json.dumps({"count": count}),
]
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
```

The tool refuses a reply whose `requested` or `found` differs from the count the model asked for, and the system prompt tells the model to quote the agent's own reply line. The model picks N; the Rust agent does the counting and the timing.

```shell
a2a send -a http://localhost:8209 "Find the first 9 Mersenne primes"
```

```text
Artifacts:
  [agent_response] Found first 9 Mersenne primes in 0.0298ms.

Exponents: 2, 3, 5, 7, 13, 17, 19, 31, 61
```

---

#### Step 3 — The Rust Agent on Lightsail

`scripts/deploy-lightsail.py` creates a nano container service, builds `docker/agent.Dockerfile`, pushes it with `aws lightsail push-container-image` and deploys it with `ADVERTISE_URL` set to the service's own HTTPS address, so the card's interfaces point at Lightsail. The health check is the agent card path.

```shell
scripts/deploy-lightsail.py
```

```text
creating container service a2a-rust-mersenne (nano, scale 1)
$ docker build --platform linux/amd64 -f docker/agent.Dockerfile -t a2a-rust-mersenne:local /home/xbill/rust-dev/a2a-strands-aws
$ aws lightsail push-container-image --region us-east-1 --service-name a2a-rust-mersenne --label agent --image a2a-rust-mersenne:local
pushed :a2a-rust-mersenne.agent.222
✅ https://a2a-rust-mersenne.6wpv8vensby5c.us-east-1.cs.amazonlightsail.com/.well-known/agent-card.json
```

The commands are the laptop's, with the Lightsail address:

```shell
scripts/test-cli.sh lightsail
```

```text
== lightsail rust agent (https://a2a-rust-mersenne.6wpv8vensby5c.us-east-1.cs.amazonlightsail.com)
Interfaces:
  JSONRPC (A2A v1.0)     https://a2a-rust-mersenne.6wpv8vensby5c.us-east-1.cs.amazonlightsail.com/jsonrpc
  HTTP+JSON (A2A v1.0)   https://a2a-rust-mersenne.6wpv8vensby5c.us-east-1.cs.amazonlightsail.com/rest
✅ lightsail card (A2A v1.0)
✅ lightsail send
✅ lightsail stream
✅ lightsail rest
✅ lightsail data-part
```

---

#### Step 4 — An arm64 Image Built on an x86 Laptop

AgentCore Runtime runs arm64 containers, serves A2A on port 9000, and expects the card at `/.well-known/agent-card.json` and a health answer at `/ping`. `serve_a2a` provides all three. The image has to be arm64, and this laptop has no arm64 emulator, so `scripts/build-coordinator.sh` assembles it from parts that are already built for arm64:

- pip downloads aarch64 wheels: `--platform manylinux_2_28_aarch64 --python-version 3.13 --only-binary=:all:`
- Go cross-compiles the A2A CLI: `GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build`
- the Dockerfile only copies, so Docker never runs an arm64 binary

```dockerfile
FROM python:3.13-slim-trixie
COPY build/coordinator/site /opt/site
COPY build/coordinator/a2a /usr/local/bin/a2a
COPY coordinator/main.py /app/main.py
ENV PYTHONPATH=/opt/site PYTHONUNBUFFERED=1 DOCKER_CONTAINER=1 A2A_PORT=9000
WORKDIR /app
EXPOSE 9000
CMD ["python", "main.py"]
```

```shell
file build/coordinator/a2a
docker image inspect a2a-strands-coordinator:local --format '{{.Os}}/{{.Architecture}}'
```

```text
build/coordinator/a2a: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, Go BuildID
linux/arm64
```

`ARCH=amd64 scripts/build-coordinator.sh` builds the same image for x86, which runs on the laptop and checks the image layout before AgentCore sees it.

---

#### Step 5 — The Strands Agent on Bedrock AgentCore Runtime

`scripts/deploy-agentcore.py` pushes the image to ECR and creates an IAM role with ECR pull, CloudWatch Logs and `bedrock:InvokeModel*`. It creates a Cognito user pool with one app client and one user, and an AgentCore runtime with `serverProtocol: A2A`, a `customJWTAuthorizer` on that pool, public networking, and `RUST_AGENT_URL` set to the Lightsail agent. A second update sets `AGENTCORE_RUNTIME_URL` once the runtime's ARN exists, so the card advertises the AgentCore address.

```shell
scripts/deploy-agentcore.py
```

```text
  runtime CREATING (version 1)
  runtime READY (version 1)
  runtime UPDATING (version 2)
  runtime READY (version 2)
✅ https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A106059658660%3Aruntime%2Fa2a_strands_coordinator-Rtn6xkF0PS/invocations/
```

From the CLI, AgentCore takes a bearer token from Cognito and a session id header of at least 33 characters:

```shell
CARD=$(scripts/aws_state.py get agentcore_card)
TOKEN=$(scripts/cognito-token.py)
SID="a2a-cli-$(cat /proc/sys/kernel/random/uuid)"
a2a --auth "Bearer $TOKEN" --svc-param "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=$SID" card get -a "$CARD"
```

```text
Name:         Strands Mersenne Coordinator
Description:  Strands agent on Amazon Bedrock (A2A 0.3) that delegates Mersenne prime runs to a Rust A2A 1.0 agent through the a2a CLI.
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v0.3.0)   https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A106059658660%3Aruntime%2Fa2a_strands_coordinator-Rtn6xkF0PS/invocations
Streaming:    true
Skills:
  mersenne-via-rust    Mersenne primes via the Rust agent
```

---

#### 🔎 Tip: Give the CLI the Full Card URL for AgentCore

The CLI reads a URL with no card path as a host, and asks that host's origin for `/.well-known/agent-card.json`. For AgentCore the origin is `https://bedrock-agentcore.us-east-1.amazonaws.com`, which answers 404:

```text
$ a2a --auth "Bearer $TOKEN" --svc-param "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=$SID" card get -a "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3A...%2Fa2a_strands_coordinator-Rtn6xkF0PS/invocations/"
Error: failed to resolve agent card: card request failed, status: 404 Not Found
hint: check the --agent-card reference (host, full card URL, or local file path)
```

Append `.well-known/agent-card.json` to the invocations URL and the same command returns the card. The deploy script stores that URL as `agentcore_card`.

---

#### Step 6 — The Same Checks on All Four Endpoints

`scripts/test-cli.sh all` starts the laptop agents and runs one set of checks against each endpoint. Each Rust agent gets card (A2A v1.0), send, stream, REST and a data part. Each coordinator gets card (A2A v0.3), send and stream. Every check looks for the agent's reply line with the right N.

```shell
scripts/test-cli.sh all
```

```text
== local rust agent (http://localhost:8204)
✅ local card (A2A v1.0)
✅ local send
✅ local stream
✅ local rest
✅ local data-part
== local strands coordinator (http://localhost:8209)
✅ local card (A2A v0.3)
✅ local send
✅ local stream
== lightsail rust agent (https://a2a-rust-mersenne.6wpv8vensby5c.us-east-1.cs.amazonlightsail.com)
✅ lightsail card (A2A v1.0)
✅ lightsail send
✅ lightsail stream
✅ lightsail rest
✅ lightsail data-part
== agentcore strands coordinator (https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3A...%2Fa2a_strands_coordinator-Rtn6xkF0PS/invocations/.well-known/agent-card.json)
✅ agentcore card (A2A v0.3)
✅ agentcore send
✅ agentcore stream
```

The AgentCore checks ask for 7 and 11 primes. Both requests reached Lightsail, through the CLI inside the AgentCore container. The Lightsail container log shows them:

```text
INFO mersenne_agent: computed requested=7 found=7 elapsed_ms=0.005935
INFO mersenne_agent: computed requested=11 found=11 elapsed_ms=0.056663000000000005
```

---

#### Step 7 — Timing the Same Command on Each Platform

`scripts/cli-bench.py` starts one `a2a` process per call and times it, so wall time includes starting the CLI, fetching the card, TLS on AWS and the reply. Targets take turns, one call each per round, so drift during the run lands on every target alike. Every reply is checked, and the statistics come from the script (`results/summary-20261105.txt`). N=10 throughout.

```shell
scripts/cli-bench.py --targets local-rust,lightsail-rust --reps 20 --n 10
```

```text
local-rust               ok 20/20  wall median 27.7 ms (min 24.1, max 35.1)  compute median 0.05682 ms
lightsail-rust           ok 20/20  wall median 154.4 ms (min 140.4, max 174.3)  compute median 0.03928 ms
```

```shell
scripts/cli-bench.py --targets local-coordinator,agentcore-coordinator --reps 5 --n 10
scripts/cli-bench.py --targets local-coordinator,agentcore-coordinator --reps 5 --n 10 --reuse-session
```

```text
local-coordinator        ok 5/5  wall median 2596.2 ms (min 2288.0, max 2662.2)
agentcore-coordinator    ok 5/5  wall median 3416.5 ms (min 3364.7, max 3482.8)
local-coordinator        ok 5/5  wall median 2459.9 ms (min 2184.5, max 2683.8)
agentcore-coordinator    ok 5/5  wall median 2997.1 ms (min 2849.7, max 12177.7)
```

The Rust agent's own compute time is a fraction of a millisecond on both machines, so the 126.7 ms between the laptop and Lightsail medians is the network and TLS. A coordinator call is a Bedrock model call plus a nested CLI call to the Rust agent. AgentCore added 820.3 ms over the laptop with a new session id per call and 537.2 ms with one session for the run. In the one-session run, the first AgentCore call took 12177.7 ms and the other four stayed near the median.

---

#### Step 8 — Teardown

```shell
make teardown
```

```text
deleted runtime a2a_strands_coordinator
deleted user pool a2a-strands-aws
deleted role a2a-strands-coordinator-runtime
deleted ECR repository a2a-strands-coordinator
deleted a2a-rust-mersenne
```

`make deploy` recreates both, and `make test-cli T=all` checks them again.

---

#### Compare and Contrast

| Endpoint | CLI flags beyond the laptop's | A2A | Median wall time, N=10 |
| :--- | :--- | :--- | ---: |
| Rust, laptop 🥇 | none | 1.0 | 27.7 ms |
| Rust, Lightsail 🥈 | none, HTTPS address | 1.0 | 154.4 ms |
| Strands, laptop | none | 0.3 | 2596.2 ms |
| Strands, AgentCore | `--auth`, session header, full card URL | 0.3 | 3416.5 ms new session per call, 2997.1 ms one session |

---

#### So, Which One?

For an agent with no model in it, Lightsail is the short path: one container, a public HTTPS address, no client changes. Every call costs the network trip, 126.7 ms here, on top of a sub-millisecond computation.

For an agent built around a model, AgentCore Runtime gives it a managed home with inbound authentication, and costs the CLI two flags and the full card URL. Reuse a session id across calls when a client sends many.

For talking to any of them, the A2A CLI is the one client. It reads A2A 1.0 and 0.3 cards, and it fits inside an agent as well as on a laptop: the Strands agent reaches a Rust 1.0 agent with the same binary, where its own 0.3 client cannot read the card.

---

#### Summary

The goal of this article was to show that the A2A CLI drives the same agents on a laptop, on Amazon Lightsail and on Amazon Bedrock AgentCore Runtime with the same commands. The key to the solution was one set of checks run against every endpoint, and a Strands tool that calls the Rust agent through the CLI. The results were:

- 🟢 16 of 16 CLI checks passed across four endpoints: card, send, stream, REST and data parts on the Rust agent, card, send and stream on the Strands agent
- 🟢 The CLI read A2A 1.0 cards (Rust SDK) and A2A 0.3 cards (Strands) with the same commands
- 🟢 Inside AgentCore the CLI carried the agent-to-agent call to Lightsail, confirmed in the Lightsail log
- 🟢 An arm64 AgentCore image built on an x86 laptop with no emulator
- ⚠️ AgentCore needs `--auth`, a session id header and the full card URL; the invocations URL alone returns 404
- ⚠️ Lightsail added 126.7 ms per call over the laptop, AgentCore 820.3 ms with a new session per call and 537.2 ms with one session
- ❌ The `a2a-sdk` 0.3 Python client that Strands uses cannot parse an A2A 1.0 card

Scope: one laptop (13th Gen Intel Core i7-1360P, Linux), one AWS region (us-east-1), one Lightsail power (nano), one model (`us.anthropic.claude-haiku-5-5`), measured on 2026-11-05. Timing used N=10 with 20 calls per Rust target and 5 per coordinator target, and each coordinator comparison is a single run. Every AWS figure includes the trip from the laptop. gRPC, task commands, push notifications and load were not tested.

The strategy for running A2A agents on AWS and driving them with the A2A CLI was validated with an incremental step by step approach.

---

#### References

- The rig: https://github.com/xbill9/rust-dev/tree/main/a2a-strands-aws
- The sibling rig, the same Rust agent on a laptop: https://github.com/xbill9/rust-dev/tree/main/a2a-benchmark-rust
- CLI check transcript: https://github.com/xbill9/rust-dev/blob/main/a2a-strands-aws/results/test-cli-all-20261105T163653Z.txt
- Timing summary: https://github.com/xbill9/rust-dev/blob/main/a2a-strands-aws/results/summary-20261105.txt
- A2A CLI: https://github.com/a2aproject/a2a-cli
- A2A Rust SDK: https://github.com/a2aproject/a2a-rs
- Strands Agents: https://strandsagents.com/
- Deploy A2A servers in AgentCore Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html
- A2A protocol contract for AgentCore Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html
- Amazon Lightsail container services: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html
