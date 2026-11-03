# a2a-benchmark-rust

Rust A2A v1.0 Mersenne prime agents + benchmark. See README.md.

- Official SDK crates: `a2a-lf` (as `a2a`), `a2a-server-lf` (as `a2a_server`), `a2a-client-lf` (as `a2a_client`), from github.com/a2aproject/a2a-rs.
- Ports: 8104 native SDK agent, 8105 `a2a server --exec` wrapping `mersenne-exec`, 8106 `adk api_server --a2a` (rust_bench), 8107 `adk web`.
- A2A CLI (`a2a`, Go, v0.3.1) is the reference client: `scripts/test-cli.sh`.
- Data parts round-trip through protobuf `Struct`: integers arrive as floats (`6.0`). Read numbers with `as_f64`.
- Benchmark statistics are computed in `mersenne-bench`, never by hand. Quote `results/*.json`.
- Run benchmarks via `scripts/bench.sh` (`MIN`/`MAX`/`REPS` env vars); calling `mersenne-bench` directly defaults `--out` to `results.json` in the repo root. `results/` is committed.
- `scripts/start-all.sh` (called by `test-cli.sh` and `bench.sh`) rebuilds and restarts both agents every time, so they always serve the current code.
- Keep the reply line `Found first N Mersenne primes in X.XXXXms.` unchanged: `scripts/test-cli.sh` greps for it.
- Before committing: `cargo fmt && cargo clippy --all-targets && cargo test --release && scripts/test-cli.sh`.
- ADK coordinator lives in `adk/rust_bench/` (Python, `google-adk` 2.13.0 in the pyenv Python, Gemini on Vertex via `scripts/adk-env.sh`). `adk api_server --a2a` must run from the rig root with agents dir `adk`; it serves only agent folders that contain `agent.json`.
- ADK checks: `scripts/test-adk.sh` (calls Gemini). `scripts/check-adk-reply.py` verifies the model's `run_benchmark` arguments and that every number it quotes came from the tool; keep tool values pre-rounded so the model never rounds.
- `serve-exec.sh` needs `--advertise-address http://localhost:8105` (ADK rejects cross-origin card URLs) and `--chunk=$'\n'` (without it stream requests fail and ADK errors). `mersenne-exec` prints the JSON line first, the summary last: ADK shows only the final chunk.
- Compare compute times only between equally paced runs: idle gaps between calls slow large-N compute (`--gap-ms`, `results/gap-*.json`).
- `start-all.sh` stops only the Rust agents (`stop-all.sh --rust-only`); `stop-all.sh` with no flag also stops ADK.
- Never put a `pkill -f` pattern from `stop-all.sh`/`start-adk.sh` (`a2a server --exec`, `adk api_server --a2a --port 8106`) in an inline shell command, even inside a heredoc or sed: it matches the shell itself and kills it. Run the scripts in their own command.
