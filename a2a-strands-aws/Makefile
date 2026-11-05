# a2a-strands-aws: thin wrappers over cargo and scripts/.
#   make test-cli T=all        make bench TARGETS=local-rust,lightsail-rust REPS=20
.DEFAULT_GOAL := help
SHELL := /bin/bash
export RUSTUP_TOOLCHAIN ?= stable

T       ?= local
TARGETS ?= local-rust,lightsail-rust
REPS    ?= 10
N       ?= 10

.PHONY: help build test fmt clippy check start stop test-cli bench \
        image deploy-lightsail deploy-agentcore deploy teardown state

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

build: ## cargo build --release
	cargo build --release

test: ## cargo test --release
	cargo test --release

fmt: ## cargo fmt
	cargo fmt

clippy: ## cargo clippy --all-targets
	cargo clippy --all-targets

check: fmt clippy test test-cli ## Pre-commit: fmt, clippy, test, local test-cli

start: ## Start the Rust agent :8204 + Strands coordinator :8209
	scripts/start-local.sh

stop: ## Stop the local agents
	scripts/stop-local.sh

test-cli: ## a2a CLI checks, T=local|lightsail|agentcore|all
	scripts/test-cli.sh $(T)

bench: ## Interleaved a2a CLI timing (TARGETS, REPS, N)
	scripts/cli-bench.py --targets $(TARGETS) --reps $(REPS) --n $(N)

image: ## Build the arm64 coordinator image
	scripts/build-coordinator.sh

deploy-lightsail: ## Rust agent -> Lightsail container service
	scripts/deploy-lightsail.py

deploy-agentcore: ## Strands coordinator -> AgentCore Runtime (+ ECR, IAM, Cognito)
	scripts/deploy-agentcore.py

deploy: deploy-lightsail deploy-agentcore ## Both

teardown: ## Delete every AWS resource the rig created
	scripts/deploy-agentcore.py --delete
	scripts/deploy-lightsail.py --delete

state: ## Show .aws-state.json (no password)
	scripts/aws_state.py show
