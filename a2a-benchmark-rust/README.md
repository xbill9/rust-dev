# a2a-benchmark-rust

A Rust follow-up to [`a2a-benchmark`](https://github.com/xbill9/a2a-benchmark): the same Mersenne prime workload (Lucas-Lehmer over the first N known exponents), built on the official A2A Rust SDK, driven with the [A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/) and coordinated by an [ADK](https://google.github.io/adk-docs/) agent run with the ADK CLI.

| Agent | Port | How it speaks A2A |
|---|---|---|
| `mersenne-agent` (native) | 8104 | Official Rust SDK: `a2a-lf` + `a2a-server-lf`, JSON-RPC at `/jsonrpc`, HTTP+JSON at `/rest` |
| `mersenne-exec` (exec) | 8105 | A2A-unaware stdin/stdout Rust program, served by `a2a server --exec --chunk` (Steps 3–4 of the CLI introduction) |
| `rust_bench` (ADK) | 8106 | Python ADK `LlmAgent` on Gemini, served by `adk api_server --a2a`; delegates to the two Rust agents over A2A |
| `adk web` dev UI | 8107 | ADK CLI web UI for `rust_bench` |

All A2A traffic is Protocol v1.0. `mersenne-bench` is the benchmark client, built on `a2a-client-lf`.

```
a2a CLI ──► adk api_server --a2a (:8106) ──Gemini──► RemoteA2aAgent ──► mersenne-agent (:8104)
                    rust_bench                                     └──► a2a server --exec (:8105) ──► mersenne-exec
                        └── run_benchmark tool ──► mersenne-bench ──► both Rust agents
```

#### Versions

| Component | Version |
|---|---|
| `a2a-lf` / `a2a-server-lf` / `a2a-client-lf` | 0.4.2 / 0.5.3 / 0.2.9 |
| `axum` / `tokio` / `num-bigint` | 0.8.9 / 1.54.1 / 0.5.1 |
| A2A CLI (`a2a`) | v0.3.1 |
| ADK CLI (`google-adk`) / `a2a-sdk` | 2.13.0 / 1.3.0 |
| Model | `gemini-3.5-flash` on Vertex AI (`MODEL_NAME` overrides) |

Rust edition 2024. The `a2a-*-lf` crates come from [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs).

---

#### Step 1 — Install the CLIs

```bash
go install github.com/a2aproject/a2a-cli@latest
mv "$(command -v a2a-cli)" "$(dirname "$(command -v a2a-cli)")/a2a"   # or copy it onto PATH
pip install -U "google-adk[a2a]"
a2a version && adk --version
```

ADK uses Gemini on Vertex AI with application-default credentials (`gcloud auth application-default login`). `scripts/adk-env.sh` sets `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_LOCATION=global`, and `GOOGLE_CLOUD_PROJECT` (from the environment, else `~/project_id.txt`).

#### Step 2 — Build and test

```bash
cargo build --release
cargo test --release
echo "first 5" | target/release/mersenne-exec     # the exec program on its own
```

#### Step 3 — Serve it, then talk to it

```bash
scripts/start-all.sh       # native :8104 + a2a server --exec :8105 (logs/)
a2a card get -a http://localhost:8104
a2a send -a http://localhost:8104 "Calculate the first 20 Mersenne primes"
a2a send -a http://localhost:8104 --stream "first 12"
a2a send -a http://localhost:8104 --transport rest "first 4"
a2a send -a http://localhost:8104 --data-part '{"count": 6}'
a2a send -a http://localhost:8105 "Calculate the first 20 Mersenne primes"
```

`scripts/test-cli.sh` runs these and checks each reply.

#### Step 4 — Put ADK in front

```bash
scripts/adk-run.sh "Use the native agent to find the first 12 Mersenne primes"   # adk run, one shot
scripts/adk-run.sh                                                                # adk run, interactive
scripts/adk-web.sh                                                                # adk web on :8107
scripts/start-adk.sh                                                              # adk api_server --a2a on :8106
```

With `adk api_server --a2a` running, the A2A CLI talks to the ADK agent like any other:

```bash
CARD=http://localhost:8106/a2a/rust_bench/.well-known/agent-card.json
a2a card get -a $CARD
a2a send -a $CARD "Find the first 9 Mersenne primes with the exec agent"
a2a send -a $CARD --stream "first 7 with the native agent"
a2a send -a $CARD "Benchmark both agents for N=1 to 18 with 5 reps"
```

```
History:
  [user] Use the native agent to find the first 12 Mersenne primes
  [agent] {"args":{"agent_name":"native_rust_agent"},"id":"call_1077783","name":"transfer_to_agent"}
  [agent] {"id":"call_1077783","name":"transfer_to_agent","response":{"result":null}}
  [agent] Found first 12 Mersenne primes in 0.0814ms. {"elapsed_ms":0.081399,...,"found":12,"requested":12}
```

Single calculations are handed to a Rust agent with `transfer_to_agent`. Benchmarks go through the `run_benchmark` tool, which runs `mersenne-bench` and returns medians already computed and rounded; the instruction tells the model to quote them, never compute. `scripts/check-adk-reply.py` enforces that on a reply: exactly one `run_benchmark` call, with the arguments the user asked for, and every number in the answer a value the tool returned. `scripts/test-adk.sh` runs all of the above.

#### Step 5 — Benchmark

```bash
scripts/bench.sh                    # N=1..22, 5 reps, native + exec
REPS=20 scripts/bench.sh            # more reps
ADK=1 REPS=3 scripts/bench.sh       # adds the ADK series (Gemini routes each call to native)
target/release/mersenne-bench --gap-ms 1300 --agent native=http://localhost:8104   # pace calls
```

Each call records `compute`, the agent's own Lucas-Lehmer time read from its structured report, and `RTT`, the round trip seen by the client. `overhead` is RTT minus compute, per call. `mersenne-bench` computes medians, minimums and maximums and writes `results/bench-<timestamp>.json` and `.md`.

---

#### Results

2026-11-03, 13th Gen Intel Core i7-1360P (16 threads), Linux, release build, every agent and the client on one machine.

Direct calls, medians of 20 reps (`results/bench-20261103T200810Z.json`):

| N | native compute ms | native RTT ms | exec compute ms | exec RTT ms |
|---|---:|---:|---:|---:|
| 1 | 0.0009 | 0.834 | 0.0006 | 3.979 |
| 10 | 0.0388 | 0.766 | 0.0424 | 4.054 |
| 15 | 1.2912 | 2.194 | 2.2317 | 7.382 |
| 18 | 15.9953 | 16.919 | 22.2887 | 27.283 |
| 20 | 26.0751 | 26.922 | 62.4932 | 66.884 |
| 22 | 181.1740 | 182.348 | 271.2701 | 274.464 |

Through ADK, medians of 3 reps (`results/bench-20261103T202430Z.json`), each request routed by Gemini to the native agent:

| N | adk compute ms | adk RTT ms |
|---|---:|---:|
| 1 | 0.0025 | 1415.209 |
| 10 | 0.0441 | 1680.943 |
| 20 | 65.4157 | 1119.595 |
| 22 | 270.5966 | 1433.557 |

Native agent called directly, with and without a 1.3 s idle gap before each call, medians of 5 reps (`results/gap-20261103-native-*.json`):

| N | no gap compute ms | 1.3 s gap compute ms |
|---|---:|---:|
| 18 | 18.7469 | 24.5951 |
| 20 | 26.0747 | 68.0913 |
| 22 | 180.6698 | 269.2014 |

- 🟢 Native SDK agent: 0.33–1.14 ms of protocol overhead per call (20-rep run).
- ⚠️ `a2a server --exec`: 3.3–5.1 ms per call, which includes starting a process per message.
- ⚠️ ADK in front: 1054–1681 ms of overhead per call, which is the Gemini round trip that picks the sub-agent.
- ⚠️ Spacing between calls slows large-N compute. The same native process takes 68.09 ms at N=20 when calls arrive 1.3 s apart, against 26.07 ms back to back, which matches the exec and ADK series. Compare compute times only between runs paced the same way. The CPU-level cause (clock scaling or core placement on this hybrid CPU) is untested.
- 🟢 Routing and quoting: 10 of 10 checked ADK benchmark requests (varied ranges and reps) sent the requested arguments and quoted only tool values; 10 of 10 unnamed "Calculate the first N" requests went to `native_rust_agent`.

#### 🔎 Tip: two `a2a server --exec` flags matter to ADK

- `--advertise-address http://localhost:8105`. The exec server otherwise advertises `127.0.0.1`, and ADK's `RemoteA2aAgent` rejects a card whose RPC URL has a different origin from where the card was fetched.
- `--chunk=$'\n'`. Without it the exec server advertises streaming but answers stream requests with `UNSUPPORTED_OPERATION`; the Go `a2a` CLI falls back to polling, and ADK's Python client fails. With it, each output line streams as its own chunk and ADK shows the last one, so `mersenne-exec` prints its JSON report first and the summary line last.

#### Compatibility with `~/a2a-benchmark`

The original runner (`run_full_benchmark.py`) posts v0.3 `message/send` to `http://localhost:8104/`. These agents speak v1.0, so that runner needs updating before it can call them; `mersenne-bench`, the `a2a` CLI and the ADK agent work as they are. The summary line keeps the original format, `Found first N Mersenne primes in X.XXXXms.`

#### Layout

```
src/lib.rs                   Lucas-Lehmer workload + Report (shared)
src/bin/mersenne-agent.rs    native A2A v1.0 agent (a2a-server-lf)
src/bin/mersenne-exec.rs     stdin/stdout program for a2a server --exec
src/bin/mersenne-bench.rs    benchmark client (a2a-client-lf)
adk/rust_bench/              ADK coordinator: agent.py, agent.json (A2A card for --a2a)
scripts/                     serve, start/stop, adk run/web, CLI + ADK tests, reply checker, bench
results/                     benchmark output
```

#### References

- [Introducing the A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/)
- [a2aproject/a2a-cli](https://github.com/a2aproject/a2a-cli)
- [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs)
- [Agent Development Kit](https://google.github.io/adk-docs/)
- [xbill9/a2a-benchmark](https://github.com/xbill9/a2a-benchmark)
