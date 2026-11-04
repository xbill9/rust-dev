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
| A2A protocol | 1.0 (spec v1.0.1; cards carry `Major.Minor` only, per spec §3) |
| `a2a-lf` / `a2a-server-lf` / `a2a-client-lf` | 0.4.2 / 0.5.3 / 0.2.9 |
| `axum` / `tokio` / `num-bigint` | 0.8.9 / 1.54.1 / 0.5.1 |
| Rust | 1.99.1, edition 2024 |
| A2A CLI (`a2a`) | v0.3.1 |
| ADK CLI (`google-adk`) / `a2a-sdk` / `google-genai` | 2.13.0 / 1.3.0 / 2.34.0 |
| Model | `gemini-3.8-flash` on Vertex AI (`MODEL_NAME` overrides) |

Every direct crate dependency is at its latest crates.io release (checked 2026-11-03). The one transitive crate behind, `matchit` 0.8.4, is pinned exactly (`=0.8.4`) by axum 0.8.9. The `a2a-*-lf` crates come from [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs).

---

#### Step 0 — A tour of the A2A CLI

`scripts/cli-tour.sh` walks the `a2a` CLI through this rig and records every command with its output: the echo server, the native agent (card, send, stream, REST, data part, JSON output), task commands (`task get`, `task list`, `--async`, `task get --wait`), the exec-wrapped program, and the ADK coordinator. The latest transcript is `results/cli-tour-20261103T214445Z.md`. A sample:

```console
$ a2a task get -a http://localhost:8104 01a1a35f-2dc0-74c0-a8aa-c6a258430da7
Status:   working (2026-11-03T21:44:46Z)
$ a2a task get -a http://localhost:8104 01a1a35f-2dc0-74c0-a8aa-c6a258430da7 --wait --poll-interval 500ms
Status:   completed (2026-11-03T21:44:47Z)
  Found first 25 Mersenne primes in 1503.4420ms.
```

(Excerpt; the task was started with `a2a send --async 'first 25'`.)

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
scripts/bench.sh                    # N=1..26 (whole exponent table), 5 reps, native + exec
REPS=20 scripts/bench.sh            # more reps
ADK=1 REPS=3 scripts/bench.sh       # adds the ADK series (Gemini routes each call to native)
target/release/mersenne-bench --gap-ms 1300 --agent native=http://localhost:8104   # pace calls
```

Each call records `compute`, the agent's own Lucas-Lehmer time read from its structured report, and `RTT`, the round trip seen by the client. `overhead` is RTT minus compute, per call. `mersenne-bench` computes medians, minimums and maximums and writes `results/bench-<timestamp>.json` and `.md`.

A call counts only if its report answers the question asked: `requested` equals N and `found` equals min(N, 26). When an LLM is in the path, the reply must show a `transfer_to_agent` to a Rust agent, so the timing comes from the agent and never from model text. Each row records `report_source` (`data` part or `text` line) and `routed_to`. Compute prints with four significant figures, so sub-microsecond medians stay visible.

---

#### Results

2026-11-03, 13th Gen Intel Core i7-1360P (16 threads), Linux, release build, every agent and the client on one machine.

Direct calls, N=1..26, medians of 20 reps (`results/bench-20261103T211408Z.json`):

| N | native compute ms | native RTT ms | exec compute ms | exec RTT ms |
|---|---:|---:|---:|---:|
| 1 | 0.001039 | 0.732 | 0.0004555 | 4.047 |
| 10 | 0.04249 | 0.858 | 0.04200 | 4.432 |
| 20 | 26.33 | 27.173 | 60.21 | 64.750 |
| 22 | 181.1 | 182.344 | 264.6 | 268.108 |
| 23 | 290.1 | 291.441 | 374.6 | 378.533 |
| 24 | 781.1 | 782.366 | 868.9 | 872.603 |
| 25 | 1625 | 1626.637 | 1625 | 1628.745 |
| 26 | 2484 | 2485.911 | 2619 | 2622.511 |

Through ADK, N=1..26, medians of 3 reps, one run per model (`results/bench-20261103T211814Z.json` on `gemini-3.5-flash`, `results/bench-20261103T213900Z.json` on `gemini-3.8-flash`). In both runs all 26 ADK rows were routed to `native_rust_agent` and read from its data part:

| N | 3.5-flash compute ms | 3.5-flash RTT ms | 3.8-flash compute ms | 3.8-flash RTT ms |
|---|---:|---:|---:|---:|
| 1 | 0.002051 | 1665.053 | 0.002615 | 2073.666 |
| 10 | 0.04513 | 1394.245 | 0.04390 | 2458.155 |
| 20 | 72.95 | 1332.994 | 68.52 | 2336.569 |
| 22 | 279.8 | 1868.178 | 287.3 | 2679.324 |
| 24 | 869.2 | 2039.514 | 879.3 | 3323.360 |
| 26 | 2226 | 3455.492 | 2241 | 4123.353 |

Native agent called directly, with and without a 1.3 s idle gap before each call, medians of 5 reps (`results/gap-20261103-native-*.json`):

| N | no gap compute ms | 1.3 s gap compute ms |
|---|---:|---:|
| 18 | 18.7469 | 24.5951 |
| 20 | 26.0747 | 68.0913 |
| 22 | 180.6698 | 269.2014 |

- 🟢 Every row through N=26 in all three series reports `found` = min(N, 26).
- 🟢 Native SDK agent: 0.55–1.40 ms of protocol overhead per call.
- ⚠️ `a2a server --exec`: 3.3–5.0 ms per call, which includes starting a process per message.
- ⚠️ ADK in front: the Gemini round trip that picks the sub-agent adds a median of 1328 ms per call on `gemini-3.5-flash` and 2283 ms on `gemini-3.8-flash` (medians of the per-N medians). The 3.8-flash run also had long tails: one N=9 call took 29.0 s. One run of 3 reps per model on a shared endpoint; rerun before quoting the model difference.
- ⚠️ Spacing between calls slows mid-range compute. The same native process takes 68.09 ms at N=20 when calls arrive 1.3 s apart, against 26.07 ms back to back, which matches the exec and ADK series. By N=25 the gap closes (native 1625, exec 1625). Compare compute times only between runs paced the same way. The CPU-level cause (clock scaling or core placement on this hybrid CPU) is untested.
- 🟢 Routing and quoting (`scripts/adk-reliability.sh`): 10 of 10 checked ADK benchmark requests (varied ranges and reps) sent the requested arguments and quoted only tool values, and 10 of 10 unnamed "Calculate the first N" requests went to `native_rust_agent`, on both `gemini-3.5-flash` and `gemini-3.8-flash`. The 3.8-flash run is `results/adk-reliability-20261103T213852Z.json`.

The A2A CLI as the client (`scripts/cli-bench.py`, one `a2a send -o json` process per call, N=1..26, 5 reps direct and 3 through ADK on `gemini-3.8-flash`; `results/cli-bench-20261104T002328Z.md`):

| | median ms |
|---|---:|
| `a2a version` (process start only) | 7.17 |
| `a2a card get` native | 9.18 |
| `a2a send` overhead, native, median of per-N medians | 20.28 |
| `a2a send` overhead, exec, median of per-N medians | 17.51 |
| `a2a send` overhead, ADK, median of per-N medians | 2217.55 |

- ⚠️ The sweep times each agent in its own block. Interleaved at N=1, 30 runs each (`scripts/cli-transport.py`, `results/cli-transport-20261104T002823Z.txt`): native JSON-RPC 20.74, native REST 21.49, exec 20.81, `a2a version` 7.62 ms. From a shell the serving path makes no difference; time agents with `mersenne-bench`.
- ⚠️ CLI overhead drops to about 11 ms for N >= 21 (compute above 100 ms) on both agents. Cause untested.

#### The nine bugs from `a2a-benchmark`, checked here

The original suite's [nine bugs](https://dev.to/gde/why-did-my-benchmark-stop-at-n22-a-debugging-story-in-nine-bugs-3m2l) and where each one stands in this rig:

| Bug in `a2a-benchmark` | Here |
|---|---|
| `str()` of 6,002-digit primes crashed Python at N ≥ 24; the run was cut to N=22 | 🟢 no prime is converted to text; default range is the whole table, 1..26; tests cover all 26 and every prime exponent ≤ 9941 |
| Go formatted primes inside the timed region | 🟢 timed region is Lucas-Lehmer plus pushing a `u64` |
| `time.time()` wall clock | 🟢 `std::time::Instant`, monotonic |
| Timing regexed out of LLM prose | 🟢 read from the agent's data part or JSON line; LLM-path calls must show a transfer to a Rust agent |
| Agents echoed the requested count | 🟢 `found` is reported and checked against min(N, 26); oversized counts saturate instead of falling back to 5 |
| `%.2f` turned sub-10 µs runs into `0.00` | 🟢 full precision in `results/`, four significant figures in tables and in the ADK tool |
| Direct and LLM pipelines on one chart | 🟢 separate series and tables, ADK labelled as Gemini-routed |
| Go's `ns` suffix unknown to the parser | 🟢 timing travels as a number in ms, no unit parsing |
| Reused `contextId` let Gemini say "I already did that" | 🟢 every request goes without a `contextId`, so each gets a fresh ADK session |

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
scripts/                     serve, start/stop, adk run/web, CLI tour, CLI + ADK tests, reply checker, reliability, bench
results/                     benchmark output
```

#### References

- [Introducing the A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/)
- [a2aproject/a2a-cli](https://github.com/a2aproject/a2a-cli)
- [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs)
- [Agent Development Kit](https://google.github.io/adk-docs/)
- [xbill9/a2a-benchmark](https://github.com/xbill9/a2a-benchmark)
