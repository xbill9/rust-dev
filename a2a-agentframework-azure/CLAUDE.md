# a2a-agentframework-azure

Sibling of `../a2a-strands-aws` and `../a2a-benchmark-rust` on Azure: the same Rust A2A v1.0 Mersenne agent on Azure Container Apps, a Microsoft Agent Framework coordinator (A2A 1.0, Azure OpenAI model) on Container Apps behind Entra ID, and the same `a2a` CLI commands against both and against localhost. See README.md.

- Ports: 8304 Rust agent, 8309 coordinator (local). Both containers listen on 8080 in Container Apps.
- `src/lib.rs` and `src/bin/mersenne-agent.rs` are copies from `../a2a-strands-aws` (port changed). Keep the reply line `Found first N Mersenne primes in X.XXXXms.`: every check greps for it.
- Agent Framework's A2A package (`agent-framework-a2a`) needs `a2a-sdk` 1.x; the shared pyenv Python carries 0.3 for the Strands rig. `scripts/start-local.sh` installs `coordinator/requirements.txt` into `build/local-site` with `pip --target` and runs the coordinator with `PYTHONPATH=build/local-site`. Never install the 1.x SDK into the shared Python, and no virtualenvs.
- The coordinator's tool calls the Rust agent with the `a2a-sdk` 1.x client (data part in, data part out). No `a2a` CLI in the image.
- `WholeTextA2AExecutor` (coordinator/main.py) is load-bearing: the Responses client ends each stream with a whole-text update, and plain `A2AExecutor` appends it, so every reply arrives twice. `test-cli.sh` (`once`/`undoubled`) and `cli-bench.py` fail on a repeated reply line.
- Deploy scripts wait until the new revision is the only one with replicas (`wait_revision`): an old revision keeps answering, 401s included, while it deprovisions.
- Model access is Entra ID only (`DefaultAzureCredential`): `az login` locally, the rig's user-assigned identity in the cloud (`AZURE_CLIENT_ID`). No API keys.
- Azure ids and URLs live in `.azure-state.json` (gitignored, 0600). `scripts/azure_state.py show` prints them. Region eastus2, resource group `a2a-agentframework-azure-rg`.
- Deploy order: `scripts/deploy-model.py` (also creates resource group, ACR, identity, Container Apps env), `scripts/deploy-rust.py`, `scripts/deploy-coordinator.py`. `scripts/teardown.py` deletes the app registration and the resource group, then purges the soft-deleted AIServices account.
- Coordinator inbound auth is Container Apps built-in auth (Microsoft provider, Return401): `a2a --auth "Bearer $(scripts/entra-token.py)" ...`. The token is the Azure CLI's, for `api://<app id>`; the app registration pre-authorizes the Azure CLI client id.
- Never put a `pkill -f`/`pgrep -f` pattern naming these programs in an inline shell command (or a heredoc in it): it matches the shell itself. `stop-local.sh` stops by PID file.
- Checks: `scripts/test-cli.sh [local|aca-rust|aca-coordinator|all]`. Timing: `scripts/cli-bench.py` (interleaved, statistics computed in the script, JSON in `results/`). Quote `results/*.json`, never a hand calculation; `scripts/summarize-results.py > results/summary-<date>.txt` computes the README's figures and differences.
- Before committing: `cargo fmt && cargo clippy --all-targets && cargo test --release && scripts/test-cli.sh`.
