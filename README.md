# rust-dev

Rust A2A rigs, one self-contained Cargo project per directory, each driven by the [A2A CLI](https://github.com/a2aproject/a2a-cli).

| Rig | What it is |
|---|---|
| [`a2a-benchmark-rust`](a2a-benchmark-rust/) | Mersenne prime workload as a native a2a-rs SDK agent (:8104) and an `a2a server --exec` program (:8105), plus a benchmark client |
| [`a2a-strands-aws`](a2a-strands-aws/) | The same Rust agent on Lightsail (:8204 locally) and a Strands coordinator on Bedrock AgentCore Runtime (:8209 locally), all driven by the same A2A CLI commands |
| [`a2a-agentframework-azure`](a2a-agentframework-azure/) | The same Rust agent on Azure Container Apps (:8304 locally) and a Microsoft Agent Framework coordinator on Azure OpenAI, on Container Apps behind Entra ID (:8309 locally), all driven by the same A2A CLI commands |
