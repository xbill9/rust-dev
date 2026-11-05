# a2a-strands-aws

Sibling of `../a2a-benchmark-rust` on AWS: the same Rust A2A v1.0 Mersenne agent on Lightsail, a Strands coordinator (A2A 0.3, Bedrock model) on Bedrock AgentCore Runtime, and the same `a2a` CLI commands against both and against localhost. See README.md.

- Ports: 8204 Rust agent, 8209 Strands coordinator (local). AgentCore fixes the container port at 9000; `A2A_PORT` overrides it locally only.
- `src/lib.rs` and `src/bin/mersenne-agent.rs` are copies from `../a2a-benchmark-rust` (port changed). Keep the reply line `Found first N Mersenne primes in X.XXXXms.`: every check greps for it.
- Strands pins `a2a-sdk<0.4` (protocol 0.3). The 0.3 Python client cannot parse the Rust 1.0 card (no top-level `url`), so `coordinator/main.py`'s tool calls the Rust agent with the `a2a` CLI (`-o json --data-part`). The image carries a cross-compiled `a2a` v0.3.1.
- AgentCore runs arm64 only and this machine has no arm64 emulator. `scripts/build-coordinator.sh` fetches aarch64 wheels with pip `--platform`, cross-compiles the CLI with Go and the Dockerfile only COPYs. `ARCH=amd64` builds the same image for a local smoke test (pass AWS creds as env: `eval "$(aws configure export-credentials --format env)"`; the host's `aws login` session does not resolve inside the container).
- AWS ids, URLs and the Cognito test user's password live in `.aws-state.json` (gitignored, 0600). `scripts/aws_state.py show` prints them without the password.
- Deploy: `scripts/deploy-lightsail.py` first (the coordinator's `RUST_AGENT_URL` defaults to the Lightsail URL), then `scripts/deploy-agentcore.py`. Both take `--delete`. Region us-east-1.
- AgentCore inbound auth is Cognito JWT: `a2a --auth "Bearer $(scripts/cognito-token.py)" --svc-param X-Amzn-Bedrock-AgentCore-Runtime-Session-Id=<33+ chars>`.
- Never name a script `token.py` (or any stdlib module) in `scripts/`: Python puts the script's directory first on `sys.path` and it shadows the stdlib for every script there.
- Never put a `pkill -f`/`pgrep -f` pattern naming these programs in an inline shell command (or a heredoc in it): it matches the shell itself. `stop-local.sh` stops by PID file.
- Checks: `scripts/test-cli.sh [local|lightsail|agentcore|all]`. Timing: `scripts/cli-bench.py` (interleaved, statistics computed in the script, JSON in `results/`). Quote `results/*.json`, never a hand calculation.
- Before committing: `cargo fmt && cargo clippy --all-targets && cargo test --release && scripts/test-cli.sh`.
