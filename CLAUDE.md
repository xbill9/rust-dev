# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Monorepo of Rust A2A rigs. Each top-level directory is a self-contained Cargo project with its own `CLAUDE.md`, `scripts/` and `results/`; there is no root workspace. Run `cargo` and `scripts/*` from inside the rig directory.

- The A2A CLI (`a2a` v0.3.1, Go, at `~/.local/bin/a2a`) is the reference client for every rig. Each rig's `scripts/test-cli.sh` drives it against the live agents.
- `a2a-benchmark-rust/` is a copy of github.com/xbill9/a2a-benchmark-rust at `1821628`; it is developed here now, not upstream.
- Rigs share localhost: `a2a-benchmark-rust` owns ports 8104–8108, `a2a-strands-aws` owns 8204 and 8209, `a2a-agentframework-azure` owns 8304 and 8309. Give a new rig its own ports.
- Rust edition 2024. Formatting is rustfmt defaults; a PostToolUse hook in `.claude/settings.json` formats edited `.rs` files.
