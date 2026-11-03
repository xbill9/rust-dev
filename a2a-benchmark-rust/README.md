# a2a-benchmark-rust

A Rust follow-up to [`a2a-benchmark`](https://github.com/xbill9/a2a-benchmark): the same Mersenne prime workload (Lucas-Lehmer over the first N known exponents), now built on the official A2A Rust SDK and driven with the [A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/).

The same Rust workload runs two ways, so the benchmark compares them directly:

| Agent | Port | How it speaks A2A |
|---|---|---|
| `mersenne-agent` (native) | 8104 | Official SDK: `a2a-lf` + `a2a-server-lf`, JSON-RPC at `/jsonrpc`, HTTP+JSON at `/rest` |
| `mersenne-exec` (exec) | 8105 | A2A-unaware stdin/stdout program, served by `a2a server --exec` (Step 3 of the CLI introduction) |

Both are A2A Protocol v1.0. `mersenne-bench` is the client, built on `a2a-client-lf`.

#### Crates

| Crate | Version | Imported as |
|---|---|---|
| `a2a-lf` | 0.4.2 | `a2a` |
| `a2a-server-lf` | 0.5.3 | `a2a_server` |
| `a2a-client-lf` | 0.2.9 | `a2a_client` |
| `axum` | 0.8.9 | |
| `tokio` | 1.54.1 | |
| `num-bigint` | 0.5.1 | |

Rust edition 2024. The `a2a-*-lf` crates come from [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs).

---

#### Step 1 — Install the A2A CLI

```bash
go install github.com/a2aproject/a2a-cli@latest
mv "$(command -v a2a-cli)" "$(dirname "$(command -v a2a-cli)")/a2a"   # or copy it onto PATH
a2a version   # a2a v0.3.1 used here
```

Homebrew: `brew tap a2aproject/a2a-cli https://github.com/a2aproject/a2a-cli && brew install a2a`.

#### Step 2 — Build and test

```bash
cargo build --release
cargo test --release
echo "first 5" | target/release/mersenne-exec     # the exec program on its own
```

#### Step 3 — Serve it, then talk to it

Terminal A:

```bash
scripts/serve-native.sh    # SDK agent on :8104
scripts/serve-exec.sh      # a2a server --exec target/release/mersenne-exec on :8105
```

Terminal B:

```bash
a2a card get -a http://localhost:8104
a2a send -a http://localhost:8104 "Calculate the first 20 Mersenne primes"
a2a send -a http://localhost:8104 --stream "first 12"
a2a send -a http://localhost:8104 --transport rest "first 4"
a2a send -a http://localhost:8104 --data-part '{"count": 6}'

a2a card get -a http://localhost:8105
a2a send -a http://localhost:8105 "Calculate the first 20 Mersenne primes"
```

`scripts/start-all.sh` / `scripts/stop-all.sh` start and stop both in the background (logs in `logs/`). `scripts/test-cli.sh` runs the commands above and checks each reply.

#### Step 4 — Benchmark

```bash
scripts/bench.sh                    # N=1..22, 5 reps, both agents
MAX=20 REPS=10 scripts/bench.sh     # override range / reps
```

Each call records two numbers. `compute` is the agent's own Lucas-Lehmer time, read from the structured report (a data part for the native agent, a JSON line for exec). `RTT` is the round trip seen by the client. `overhead` is RTT minus compute, per call. Medians, minimums and maximums are computed by `mersenne-bench` and written to `results/bench-<timestamp>.json` and `.md`.

---

#### Results

One run, 2026-11-03, 13th Gen Intel Core i7-1360P (16 threads), Linux, release build, both agents and the client on the same machine, medians of 5 reps. Full rows with min/max: `results/bench-20261103T183026Z.json`.

| N | native compute ms | native RTT ms | native overhead ms | exec compute ms | exec RTT ms | exec overhead ms |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.0010 | 0.843 | 0.842 | 0.0005 | 3.895 | 3.895 |
| 5 | 0.0039 | 0.425 | 0.420 | 0.0049 | 4.180 | 4.176 |
| 10 | 0.0366 | 0.592 | 0.556 | 0.0464 | 4.643 | 4.598 |
| 15 | 1.8401 | 2.704 | 0.954 | 2.1312 | 6.401 | 4.467 |
| 18 | 17.5309 | 18.614 | 1.089 | 20.0663 | 24.252 | 4.186 |
| 20 | 26.2561 | 27.401 | 1.115 | 71.0614 | 77.561 | 4.514 |
| 21 | 103.0168 | 104.016 | 1.368 | 196.0120 | 200.718 | 3.707 |
| 22 | 181.3584 | 182.455 | 1.206 | 272.1762 | 275.472 | 3.296 |

- 🟢 Native SDK agent: 0.35–1.4 ms of protocol overhead per call across all N.
- ⚠️ Exec mode: 3.3–4.9 ms of overhead per call, the cost of starting a process per message.
- ⚠️ At N ≥ 16 the exec program's own compute time is also higher (N=20: 71 ms vs 26 ms), because each call runs in a fresh process. Five reps on a laptop CPU with performance and efficiency cores is a small sample; N=19 > N=20 on the native side shows the noise. Rerun with more reps before quoting these.

#### Compatibility with `~/a2a-benchmark`

The original runner (`run_full_benchmark.py`) posts v0.3 `message/send` to `http://localhost:8104/`. This agent speaks v1.0 at `/jsonrpc` and `/rest`, so that runner needs updating before it can call it; `mersenne-bench` or the `a2a` CLI work as they are. The summary line keeps the original format, `Found first N Mersenne primes in X.XXXXms.`

#### Layout

```
src/lib.rs                   Lucas-Lehmer workload + Report (shared)
src/bin/mersenne-agent.rs    native A2A v1.0 agent (a2a-server-lf)
src/bin/mersenne-exec.rs     stdin/stdout program for a2a server --exec
src/bin/mersenne-bench.rs    benchmark client (a2a-client-lf)
scripts/                     serve, start/stop, CLI tests, bench
results/                     benchmark output
```

#### References

- [Introducing the A2A CLI](https://a2a-protocol.org/latest/blog/2026/10/01/introducing-a2a-cli/)
- [a2aproject/a2a-cli](https://github.com/a2aproject/a2a-cli)
- [a2aproject/a2a-rs](https://github.com/a2aproject/a2a-rs)
- [xbill9/a2a-benchmark](https://github.com/xbill9/a2a-benchmark)
