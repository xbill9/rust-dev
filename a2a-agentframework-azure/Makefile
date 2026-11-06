# a2a-agentframework-azure: thin wrappers over cargo and scripts/.
#   make test-cli T=all        make bench TARGETS=local-rust,aca-rust REPS=20
.DEFAULT_GOAL := help
SHELL := /bin/bash
export RUSTUP_TOOLCHAIN ?= stable

T       ?= local
TARGETS ?= local-rust,aca-rust
REPS    ?= 10
N       ?= 10

.PHONY: help build test fmt clippy check start stop test-cli bench \
        deploy-model deploy-rust deploy-coordinator deploy teardown state

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-19s %s\n", $$1, $$2}'

build: ## cargo build --release
	cargo build --release

test: ## cargo test --release
	cargo test --release

fmt: ## cargo fmt
	cargo fmt

clippy: ## cargo clippy --all-targets
	cargo clippy --all-targets

check: fmt clippy test test-cli ## Pre-commit: fmt, clippy, test, local test-cli

start: ## Start the Rust agent :8304 + Agent Framework coordinator :8309
	scripts/start-local.sh

stop: ## Stop the local agents
	scripts/stop-local.sh

test-cli: ## a2a CLI checks, T=local|aca-rust|aca-coordinator|all
	scripts/test-cli.sh $(T)

bench: ## Interleaved a2a CLI timing (TARGETS, REPS, N)
	scripts/cli-bench.py --targets $(TARGETS) --reps $(REPS) --n $(N)

deploy-model: ## Resource group, ACR, identity, ACA env, Azure OpenAI deployment
	scripts/deploy-model.py

deploy-rust: ## Rust agent -> Azure Container Apps
	scripts/deploy-rust.py

deploy-coordinator: ## Agent Framework coordinator -> Container Apps + Entra ID auth
	scripts/deploy-coordinator.py

deploy: deploy-model deploy-rust deploy-coordinator ## All three, in order

teardown: ## Delete the app registration and the resource group
	scripts/teardown.py

state: ## Show .azure-state.json
	scripts/azure_state.py show
