# a2a-benchmark-rust

Rust A2A v1.0 Mersenne prime agents + benchmark. See README.md.

- Official SDK crates: `a2a-lf` (as `a2a`), `a2a-server-lf` (as `a2a_server`), `a2a-client-lf` (as `a2a_client`), from github.com/a2aproject/a2a-rs.
- Ports: 8104 native SDK agent, 8105 `a2a server --exec` wrapping `mersenne-exec`.
- A2A CLI (`a2a`, Go, v0.3.1) is the reference client: `scripts/test-cli.sh`.
- Data parts round-trip through protobuf `Struct`: integers arrive as floats (`6.0`). Read numbers with `as_f64`.
- Benchmark statistics are computed in `mersenne-bench`, never by hand. Quote `results/*.json`.
- Run benchmarks via `scripts/bench.sh` (`MIN`/`MAX`/`REPS` env vars); calling `mersenne-bench` directly defaults `--out` to `results.json` in the repo root. `results/` is committed.
- `scripts/start-all.sh` (called by `test-cli.sh` and `bench.sh`) rebuilds and restarts both agents every time, so they always serve the current code.
- Keep the reply line `Found first N Mersenne primes in X.XXXXms.` unchanged: `scripts/test-cli.sh` greps for it.
- Before committing: `cargo fmt && cargo clippy --all-targets && cargo test --release && scripts/test-cli.sh`.
- Do not `pkill -f "a2a server --exec"` from an inline shell command: the pattern matches the shell itself. Use `scripts/stop-all.sh`.
