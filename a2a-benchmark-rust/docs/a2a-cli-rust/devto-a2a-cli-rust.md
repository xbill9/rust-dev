---
title: "The A2A CLI and Rust: The Same Code, Three Ways to Serve It"
published: false
description: "A tour of the A2A CLI against Rust agents on A2A v1.0: the official Rust SDK, a plain stdin/stdout program wrapped by a2a server --exec, and an ADK coordinator on Gemini, each timed from the CLI and from a Rust client."
tags: rust, a2a, ai, agents
cover_image: https://raw.githubusercontent.com/xbill9/rust-dev/main/a2a-benchmark-rust/docs/a2a-cli-rust/devto-cover.dbab2d14.jpg
---

This article provides a step by step guide to the A2A CLI, driven against Rust agents that speak A2A Protocol v1.0. The same Rust code, a Lucas-Lehmer test over the first N Mersenne prime exponents, is served three ways: on the official A2A Rust SDK, as a plain stdin/stdout program wrapped by `a2a server --exec`, and behind an ADK coordinator on Gemini started with the ADK CLI. Each one is timed from the A2A CLI and from a Rust client.

https://github.com/xbill9/rust-dev/tree/main/a2a-benchmark-rust

**The A2A CLI talks to all three with the same commands, and `a2a server --exec` turns a 30-line program with no A2A code into an agent that ADK can call.** One `a2a send` from a shell takes a median 20.74 ms against the SDK agent, of which 7.62 ms is starting the CLI. From a Rust client the SDK agent adds 0.55 to 1.40 ms per call, the wrapped program 3.33 to 5.05 ms, and the ADK coordinator a median 1328 ms on `gemini-3.5-flash` and 2283 ms on `gemini-3.8-flash`. Every call through N=26 returned the right count of primes.

---

#### What Is Being Built?

| Agent | Port | How it speaks A2A |
| :--- | :--- | :--- |
| `mersenne-agent` | 8104 | Official Rust SDK, JSON-RPC at `/jsonrpc` and HTTP+JSON at `/rest` |
| `mersenne-exec` | 8105 | A stdin/stdout Rust program served by `a2a server --exec` |
| `rust_bench` | 8106 | ADK `LlmAgent` on Gemini, served by `adk api_server --a2a` |
| echo | 8108 | `a2a server --echo`, for the first command |

```text
a2a CLI ──► adk api_server --a2a (:8106) ──Gemini──► RemoteA2aAgent ──► mersenne-agent (:8104)
                    rust_bench                                     └──► a2a server --exec (:8105) ──► mersenne-exec
                        └── run_benchmark tool ──► mersenne-bench ──► both Rust agents
```

Versions, read from the machine on 2026-11-03:

| Component | Version |
| :--- | :--- |
| A2A protocol | 1.0 |
| A2A CLI (`a2a`) | v0.3.1 |
| `a2a-lf` / `a2a-server-lf` / `a2a-client-lf` | 0.4.2 / 0.5.3 / 0.2.9 |
| Rust | 1.99.1, edition 2024 |
| `google-adk` / `a2a-sdk` / `google-genai` | 2.13.0 / 1.3.0 / 2.34.0 |
| Model | `gemini-3.8-flash` on Vertex AI |

The `a2a-*-lf` crates are the official SDK from `a2aproject/a2a-rs`. Agent cards carry the protocol as `Major.Minor`, so they read `1.0`.

---

#### Step 1 — Install the A2A CLI

The CLI is one Go binary. Homebrew, WinGet and release binaries work; from source:

```shell
go install github.com/a2aproject/a2a-cli@latest
mv "$(command -v a2a-cli)" "$(dirname "$(command -v a2a-cli)")/a2a"
a2a version
```

```text
a2a v0.3.1
commit:  none
built:   unknown
go:      go1.26.3
os/arch: linux/amd64
```

`go install` names the binary `a2a-cli`; the docs and the CLI's own skill call it `a2a`.

---

#### Step 2 — Talk to an Echo Server

`a2a server --echo` starts an agent that sends back what it receives, so the client can be checked before any agent code exists:

```shell
a2a server --echo --port 8108 &
a2a send -a http://localhost:8108 "hello world from A2A"
```

```text
Task:     01a1a35f-2b2b-7f3a-92a2-e3dc6c69e359
Context:  01a1a35f-2b2c-7120-ac45-a74adab9d1d2
Status:   completed (2026-11-03T16:44:45-05:00)
Artifacts:
  [01a1a35f-2b2c-71ba-8e6c-22c4b7c210df] hello world from A2A
History:
  [user] hello world from A2A
```

Every `send` creates a task with an id, a context, a final status and its artifacts. The Go servers started by the CLI stamp local time; the Rust SDK agent stamps UTC.

---

#### Step 3 — Build and Start the Rust Agents

The rig is one Cargo project with four binaries: the SDK agent, the stdin/stdout program, the benchmark client, and a shared library holding the Lucas-Lehmer code.

```shell
git clone https://github.com/xbill9/rust-dev
cd rust-dev/a2a-benchmark-rust
cargo build --release
scripts/start-all.sh
```

```text
agents up: 8104 native, 8105 exec
```

`start-all.sh` rebuilds, stops any running copy, starts the SDK agent on 8104 and `a2a server --exec` on 8105 with logs in `logs/`, and waits until both cards answer. `scripts/test-cli.sh` runs the CLI commands below against them and checks each reply.

---

#### Step 4 — Read an Agent Card

`card get` fetches `/.well-known/agent-card.json` and prints what the agent offers:

```shell
a2a card get -a http://localhost:8104
```

```text
Name:         Mersenne Prime Agent Rust
Description:  A Rust A2A v1.0 agent (official a2a-rs SDK) that confirms the first n Mersenne primes with the Lucas-Lehmer test and reports the elapsed time.
Version:      0.1.0
Interfaces:
  JSONRPC (A2A v1.0)     http://localhost:8104/jsonrpc
  HTTP+JSON (A2A v1.0)   http://localhost:8104/rest
Streaming:    true
Skills:
  find-mersenne-rust   Find Mersenne Primes in Rust
```

The card lists two interfaces. The CLI picks one, and `--transport` chooses.

---

#### Step 5 — Send, Stream, Switch Transport, Send Data

A plain message:

```shell
a2a send -a http://localhost:8104 "Calculate the first 12 Mersenne primes"
```

```text
Status:   completed (2026-11-03T21:44:45Z)
  Found first 12 Mersenne primes in 0.0902ms.
Artifacts:
  [mersenne-report] Found first 12 Mersenne primes in 0.0902ms. {"elapsed_ms":0.090239,"exponents":[2,3,5,7,13,17,19,31,61,89,107,127],"found":12,"requested":12}
```

The `mersenne-report` artifact carries two parts: the summary as text, and the same result as a data part, so a client reads the timing from a field.

`--stream` prints each event as it arrives, here the `working` status before the result:

```shell
a2a send -a http://localhost:8104 --stream "first 8"
```

```text
[status] working
Task:     01a1a35f-2b64-77b5-9417-18b1f425b17d
Context:  01a1a35f-2b64-77b5-9417-18b24253b719
Status:   completed (2026-11-03T21:44:45Z)
  Found first 8 Mersenne primes in 0.0164ms.
```

`--transport rest` sends the same request over HTTP+JSON, and `--data-part` sends structured input:

```shell
a2a send -a http://localhost:8104 --transport rest "first 4"
a2a send -a http://localhost:8104 --data-part '{"count": 6}'
```

```text
  Found first 4 Mersenne primes in 0.0080ms.
  Found first 6 Mersenne primes in 0.0108ms.
```

---

#### 🔎 Tip: Data Parts Arrive as Floats

A2A v1.0 carries data parts as a protobuf `Struct`, whose only number type is a double. `{"count": 6}` sent by the CLI reaches the agent as `6.0`, so a strict integer field fails to deserialise. Read numbers with `as_f64` and check for a whole value:

```rust
if let PartContent::Data(v) = &part.content
    && let Some(n) = v.get("count").and_then(|n| n.as_f64())
    && n >= 1.0
    && n.fract() == 0.0
{
    return n as usize;
}
```

---

#### Step 6 — Script It With JSON Output

`-o json` prints the whole task, which pipes into anything:

```shell
a2a send -a http://localhost:8104 -o json 'first 3' | python3 -c 'import sys,json; t=json.load(sys.stdin)["task"]; print(t["status"]["state"], [p for a in t["artifacts"] for p in a["parts"] if "data" in p][0]["data"])'
```

```text
TASK_STATE_COMPLETED {'elapsed_ms': 0.007166, 'exponents': [2, 3, 5], 'found': 3, 'requested': 3}
```

---

#### Step 7 — Tasks: List, Start in the Background, Wait

The SDK agent keeps its tasks in memory, and the CLI reads them back:

```shell
a2a task list -a http://localhost:8104
```

```text
ID                                    STATUS     CONTEXT
01a1a35f-2b4f-7190-b6df-81bb7b76c2cc  completed  01a1a35f-2b4f-7190-b6df-81bca35e8b6d
01a1a35f-2b64-77b5-9417-18b1f425b17d  completed  01a1a35f-2b64-77b5-9417-18b24253b719
01a1a35f-2bab-7012-b094-1022dce75f36  completed  01a1a35f-2bab-7012-b094-1023824b35eb
```

`--async` returns as soon as the task exists. N=25 takes over a second, long enough to catch it running:

```shell
a2a send -a http://localhost:8104 --async "first 25"
```

```text
Task:     01a1a3f5-9da1-746b-abae-84307e4e1735
Context:  01a1a3f5-9da1-746b-abae-8431b422e72e
Status:   working (2026-11-04T00:29:05Z)
History:
  [user] first 25
```

`task get --wait` polls until the task finishes:

```shell
a2a task get -a http://localhost:8104 01a1a3f5-9da1-746b-abae-84307e4e1735 --wait --poll-interval 500ms
```

```text
Task:     01a1a3f5-9da1-746b-abae-84307e4e1735
Context:  01a1a3f5-9da1-746b-abae-8431b422e72e
Status:   completed (2026-11-04T00:29:06Z)
  Found first 25 Mersenne primes in 1509.7683ms.
```

---

#### Step 8 — The Native Rust Agent

The SDK agent is one `AgentExecutor`. It emits a `working` status, runs the big-integer work on a blocking thread, then returns the finished task:

```rust
let done = async move {
    // Big-integer work is CPU-bound; keep it off the async workers.
    let report = tokio::task::spawn_blocking(move || find_mersenne_primes(count))
        .await
        .map_err(|e| A2AError::internal(format!("worker panicked: {e}")))?;
    let summary = report.summary();
    let data = serde_json::to_value(&report)
        .map_err(|e| A2AError::internal(format!("serialise report: {e}")))?;
    // ... Task { status: Completed, artifacts: [Part::text(summary), Part::data(data)] }
};
Box::pin(stream::once(async { Ok(working) }).chain(stream::once(done)))
```

The server wires the SDK's routers into axum, one per transport plus the card:

```rust
let handler = Arc::new(DefaultRequestHandler::new(MersenneExecutor, InMemoryTaskStore::new()));
let card = Arc::new(StaticAgentCard::new(agent_card(&base)));

let app = axum::Router::new()
    .nest("/jsonrpc", a2a_server::jsonrpc::jsonrpc_router(handler.clone()))
    .nest("/rest", a2a_server::rest::rest_router(handler))
    .merge(a2a_server::agent_card::agent_card_router(card));
```

The Lucas-Lehmer test runs on `num-bigint` with the reduction mod 2^p − 1 done by folding the high bits onto the low ones. The timed region holds only the tests, on a monotonic clock, and no prime is ever turned into a decimal string. Two slow tests check the arithmetic: one runs the test on every prime exponent up to 9941 and asserts it accepts exactly the first 22 known ones, the other confirms all 26:

```shell
cargo test --release --lib -- --ignored
```

```text
test tests::all_26_exponents_prime ... ok
test tests::exhaustive_through_n22 ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 5 filtered out; finished in 25.70s
```

---

#### Step 9 — Serve a Plain Program With `a2a server --exec`

`mersenne-exec` knows nothing about A2A. It reads the message on stdin and prints two lines:

```shell
echo 'first 5' | target/release/mersenne-exec
```

```text
{"requested":5,"found":5,"elapsed_ms":0.007023000000000001,"exponents":[2,3,5,7,13]}
Found first 5 Mersenne primes in 0.0070ms.
```

The A2A CLI makes it an agent:

```shell
a2a server --exec "$PWD/target/release/mersenne-exec" --chunk=$'\n' \
  --name "Mersenne Prime Exec Rust" \
  --advertise-address "http://localhost:8105" --port 8105
```

The same client commands work against it:

```shell
a2a send -a http://localhost:8105 --stream "first 8"
```

```text
Status:   submitted
History:
  [user] first 8
[status] working
[artifact] {"requested":8,"found":8,"elapsed_ms":0.01543,"exponents":[2,3,5,7,13,17,19,31]}Found first 8 Mersenne primes in 0.0154ms.
[status] completed
```

The exec server starts the program once per message, hands it the text, and returns stdout as the artifact.

---

#### 🔎 Tip: Two `--exec` Flags ADK Needs

- `--advertise-address http://localhost:8105`. The exec server's card names `127.0.0.1` by default, and ADK's `RemoteA2aAgent` refuses a card whose RPC URL has a different origin from the one the card came from.
- `--chunk=$'\n'`. With it, each output line streams as its own chunk. Without it, stream requests get `UNSUPPORTED_OPERATION`: the Go CLI falls back to polling and ADK's Python client fails. ADK keeps only the last chunk, so `mersenne-exec` prints the JSON line first and the summary last.

---

#### Step 10 — Put ADK in Front

ADK needs its Python package and Gemini on Vertex AI, signed in with application-default credentials:

```shell
pip install -U "google-adk[a2a]"
gcloud auth application-default login
source scripts/adk-env.sh
```

`adk-env.sh` sets `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_LOCATION=global`, the project, and `MODEL_NAME`, which defaults to `gemini-3.8-flash`.

`adk/rust_bench/agent.py` is an ADK `LlmAgent` with both Rust agents as `RemoteA2aAgent` sub-agents and one tool:

```python
native_agent = RemoteA2aAgent(
    name="native_rust_agent",
    description="Rust A2A v1.0 agent on the official a2a-rs SDK. ...",
    agent_card=f"{NATIVE_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

root_agent = LlmAgent(
    name="rust_bench",
    model=os.getenv("MODEL_NAME", "gemini-3.8-flash"),
    tools=[run_benchmark],
    sub_agents=[native_agent, exec_agent],
)
```

The ADK CLI runs it three ways:

```shell
adk run rust_bench                                # terminal
adk web --port 8107                               # dev UI
adk api_server --a2a --port 8106 adk              # A2A server, from the rig root
```

`adk api_server --a2a` serves each agent folder that holds an `agent.json` card, at `/a2a/<name>`; `scripts/start-adk.sh` starts it in the background. The A2A CLI then treats the coordinator like any other agent:

```shell
a2a send -a http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json \
  --timeout 120s "Find the first 9 Mersenne primes with the exec agent"
```

```text
Status:   completed (2026-11-03T21:44:51Z)
Artifacts:
  [f2d2f27d-24ce-4120-8368-d966c99617a9] Found first 9 Mersenne primes in 0.0236ms.
History:
  [user] Find the first 9 Mersenne primes with the exec agent
  [agent] {"args":{"agent_name":"exec_rust_agent"},"id":"call_1332004","name":"transfer_to_agent"}
  [agent] {"id":"call_1332004","name":"transfer_to_agent","response":{"result":null}}
  [agent] {"requested":9,"found":9,"elapsed_ms":0.023635,"exponents":[2,3,5,7,13,17,19,31,61]}
  [agent] Found first 9 Mersenne primes in 0.0236ms.
```

The history shows the hand-off: Gemini calls `transfer_to_agent`, the Rust agent answers, and its JSON report comes back through two A2A hops.

---

#### Step 11 — Keep the Model Away From the Numbers

A benchmark through an LLM can time the model writing a number. Two rules keep the timing in code:

- **The benchmark client checks every reply.** `mersenne-bench` reads the timing from the agent's data part or JSON line, rejects a report where `requested` differs from N or `found` differs from min(N, 26), and rejects an LLM-path reply with no `transfer_to_agent` to a Rust agent. Each row records where its report came from and who it was routed to.
- **ADK benchmarks go through a tool.** `run_benchmark` runs `mersenne-bench` and returns medians already computed and rounded. The instruction tells Gemini to quote them, and `scripts/check-adk-reply.py` verifies a reply: one `run_benchmark` call, with the arguments asked for, and every number in the answer a value the tool returned.

A benchmark request sent from the CLI, saved with `-o json`. The tool call and the head of the answer:

```shell
a2a send -a $CARD --timeout 300s -o json "Benchmark both agents for N=3 to 6 with 2 reps" > reply.json
```

```text
[tool call] {"max_n": 6, "min_n": 3, "reps": 2}
### Arguments Used
- `min_n`: 3
- `max_n`: 6
- `reps`: 2
```

The answer goes on with a summary per agent and a row per N. The check:

```shell
scripts/check-adk-reply.py reply.json 3 6 2
```

```text
state: TASK_STATE_COMPLETED
run_benchmark calls: 1
args sent: {'max_n': 6, 'min_n': 3, 'reps': 2}  requested: {'min_n': 3, 'max_n': 6, 'reps': 2}
numbers in reply: 57  not from the tool: 0
PASS
```

`scripts/adk-reliability.sh` sends ten benchmark requests with varied ranges and ten requests that name no agent. On `gemini-3.8-flash`, 10 of 10 benchmark replies passed the checker and 10 of 10 unnamed requests went to `native_rust_agent`.

The sweep covers the whole exponent table, N=1 to 26. Exponent 23209 is a 6,987-digit number, and the arithmetic stays in `BigUint` throughout.

---

#### Step 12 — Benchmark From a Rust Client

```shell
REPS=20 scripts/bench.sh          # native + exec, N=1..26
ADK=1 REPS=3 scripts/bench.sh     # adds the ADK series
```

`mersenne-bench` is built on the SDK's client crate, `a2a-client-lf`. Each call records the agent's own compute time and the client's round trip; overhead is the round trip minus compute, per call. Direct calls, medians of 20 reps:

| N | native compute ms | native overhead ms | exec compute ms | exec overhead ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.001039 | 0.731 | 0.0004555 | 4.046 |
| 10 | 0.04249 | 0.793 | 0.04200 | 4.391 |
| 20 | 26.33 | 0.970 | 60.21 | 4.374 |
| 22 | 181.1 | 1.255 | 264.6 | 3.558 |
| 24 | 781.1 | 1.073 | 868.9 | 3.335 |
| 26 | 2484 | 1.396 | 2619 | 3.588 |

Through ADK, medians of 3 reps, one run per model. All 26 rows in each run went to `native_rust_agent` and read its data part:

| N | 3.5-flash compute ms | 3.5-flash round trip ms | 3.8-flash compute ms | 3.8-flash round trip ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.002051 | 1665.053 | 0.002615 | 2073.666 |
| 10 | 0.04513 | 1394.245 | 0.04390 | 2458.155 |
| 20 | 72.95 | 1332.994 | 68.52 | 2336.569 |
| 22 | 279.8 | 1868.178 | 287.3 | 2679.324 |
| 26 | 2226 | 3455.492 | 2241 | 4123.353 |

The slowest single call on `gemini-3.8-flash` took 29.0 s, at N=9.

---

#### Step 13 — Time the A2A CLI Itself

`scripts/cli-bench.py` runs one `a2a send -o json` process per call, the way a shell script would, and applies the same checks to each reply. Wall time covers starting the CLI, fetching the card, sending, and exiting. Two reference commands, 20 runs each:

| Command | Median ms | Min ms | Max ms |
| :--- | ---: | ---: | ---: |
| `a2a version` | 7.17 | 5.57 | 9.62 |
| `a2a card get` (native) | 9.18 | 8.30 | 11.17 |

The full sweep, N=1 to 26, 5 reps direct and 3 through ADK:

| Agent | Calls | Overhead per call, per-N medians | Median of the per-N medians |
| :--- | ---: | :--- | ---: |
| native | 130 | 10.92 to 21.82 ms | 20.28 ms |
| exec | 130 | 9.43 to 20.81 ms | 17.51 ms |
| ADK, 3.8-flash | 78 | 1825.22 to 3017.92 ms | 2217.55 ms |

Every ADK call went to `native_rust_agent`; the slowest took 22693.6 ms. The sweep times each agent in its own block, so native and exec ran minutes apart. Run in alternating order, N=1, 30 runs each (`scripts/cli-transport.py`):

```text
native, default (JSON-RPC): median 20.74 ms, min 18.60, max 26.51
native, --transport rest: median 21.49 ms, min 19.63, max 26.15
exec (HTTP+JSON only): median 20.81 ms, min 18.67, max 28.07
a2a version: median 7.62 ms, min 6.07, max 10.71
```

From a shell, the transport and the serving path make no difference to the CLI's cost: about 21 ms per call, about a third of it starting the process. Against the Rust client's 0.55 to 1.40 ms, the CLI fits scripts and checks, and the Rust client fits a benchmark.

The CLI's overhead in the sweep drops to about 11 ms for both agents once compute passes 100 ms (N=21 and up). Why is untested.

---

#### 🔎 Tip: Compare Compute Only Between Runs Paced Alike

The same native process at N=20 takes 26.07 ms when calls arrive back to back and 68.09 ms when each call follows a 1.3 s idle gap (`mersenne-bench --gap-ms 1300`). ADK's model round trip spaces calls out too, and its mid-range compute times sit close to the gap series: 68.52 ms at N=20 on `gemini-3.8-flash`. The CPU-level cause, clock scaling or core placement on a hybrid laptop CPU, is untested.

---

#### Compare and Contrast

| Serving path | Code the agent needs | Overhead from a Rust client | `a2a send` from a shell, N=1 |
| :--- | :--- | ---: | ---: |
| Official Rust SDK 🥇 | an `AgentExecutor` and three routers | 0.55 to 1.40 ms | 20.74 ms |
| `a2a server --exec` 🥈 | none: stdin in, stdout out | 3.33 to 5.05 ms | 20.81 ms |
| ADK coordinator 🥉 | an `agent.py`, an `agent.json` card | 1328 ms on 3.5-flash, 2283 ms on 3.8-flash | 2664.00 ms on 3.8-flash |

Rust-client ranges are the smallest and largest per-N medians; the ADK figures are the medians of its per-N medians. The exec figure includes starting a process for every message; how it splits between process start and the HTTP hop was not measured. At N=26 the work itself dominates every path: 2484 ms native and 2619 ms exec, direct.

---

#### So, Which One?

For an agent built to be one, use the SDK: about a millisecond of protocol cost, both transports, tasks the CLI can list and wait on.

For a program that already exists, `a2a server --exec` makes it an agent with no code change. A few milliseconds per call buys that, and ADK can call it once the two flags are set.

For routing by natural language, put ADK in front and keep the timing out of the model: a tool for anything computed, and a check that the model sent the arguments asked for.

For talking to any of them, the A2A CLI is the one client: `card get`, `send`, `--stream`, `task get --wait`, and `-o json` for scripts. Each call costs about 21 ms, so time agents from a long-lived client.

---

#### Summary

The goal of this article was to drive the A2A CLI against Rust agents on A2A v1.0, and to measure what each way of serving the same Rust code costs per call. The key to the solution was one benchmark client that reads timing from a structured report and checks that every reply answers the question asked. The results on one laptop were:

- 🟢 The A2A CLI drove all three agents with the same commands: card, send, stream, REST, data parts, JSON output, task list, `--async` and `task get --wait`
- 🟢 Every call through N=26, from the Rust client and from the CLI, reported `found` = min(N, 26)
- 🟢 The SDK agent added 0.55 to 1.40 ms per call from a Rust client
- 🟢 `a2a server --exec` served an A2A-unaware program to the CLI and to ADK
- 🟢 On `gemini-3.8-flash`, 10 of 10 benchmark replies quoted only tool values, and 10 of 10 unnamed requests went to the native agent
- ⚠️ One `a2a send` from a shell costs about 21 ms whatever the agent, 7.62 ms of it starting the CLI
- ⚠️ The wrapped program added 3.33 to 5.05 ms per call from a Rust client
- ⚠️ ADK added a median 1328 ms per call on `gemini-3.5-flash` and 2283 ms on `gemini-3.8-flash`, with one call at 29.0 s
- ❌ Compute times from calls spaced by idle gaps run slower and do not compare with back-to-back runs

Scope: one 13th Gen Intel Core i7-1360P laptop on Linux, release build, every agent and client on the same machine, 2026-11-03 and 2026-11-04. Rust-client series have 20 reps per N direct and 3 through ADK, with one run per model on Vertex AI's shared `global` endpoint, so the difference between the two Gemini models is a single sample. The CLI series has 5 reps per N direct and 3 through ADK, on `gemini-3.8-flash` only, and reliability was checked on that model only, ten requests of each kind. The gRPC transport, `task cancel`, `task subscribe`, push notifications and authentication were not exercised.

The strategy for serving and benchmarking Rust A2A agents with the A2A CLI was validated with an incremental step by step approach.

---

#### References

- The rig: https://github.com/xbill9/rust-dev/tree/main/a2a-benchmark-rust
- CLI tour transcripts: https://github.com/xbill9/rust-dev/blob/main/a2a-benchmark-rust/results/cli-tour-20261103T214445Z.md and https://github.com/xbill9/rust-dev/blob/main/a2a-benchmark-rust/results/cli-tour-20261104T002904Z.md
- CLI timing: https://github.com/xbill9/rust-dev/blob/main/a2a-benchmark-rust/results/cli-bench-20261104T002328Z.md
- Introducing the A2A CLI: https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/
- A2A CLI: https://github.com/a2aproject/a2a-cli
- A2A Rust SDK: https://github.com/a2aproject/a2a-rs
- Agent Development Kit: https://google.github.io/adk-docs/
- Why Did My Benchmark Stop at N=22?: https://dev.to/gde/why-did-my-benchmark-stop-at-n22-a-debugging-story-in-nine-bugs-3m2l
