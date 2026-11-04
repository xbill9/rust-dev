# a2a-benchmark-rust: thin wrappers over cargo and scripts/.
#   make bench REPS=20        make bench-adk REPS=3        make adk-run Q="first 12"
.DEFAULT_GOAL := help
SHELL := /bin/bash
# The lockfile needs rustc >= 1.89; the machine default may be older.
export RUSTUP_TOOLCHAIN ?= stable

MIN  ?= 1
MAX  ?= 26
REPS ?= 5
RUNS ?= 10
Q    ?=

.PHONY: help build test test-full fmt clippy check start start-adk stop \
        test-cli test-adk tour bench bench-adk cli-bench cli-transport \
        adk-run adk-web reliability summarize clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

build: ## cargo build --release
	cargo build --release

test: ## cargo test --release
	cargo test --release

test-full: ## Exhaustive correctness through N=22 (~25 s)
	cargo test --release -- --ignored

fmt: ## cargo fmt
	cargo fmt

clippy: ## cargo clippy --all-targets
	cargo clippy --all-targets

check: fmt clippy test test-cli ## Pre-commit: fmt, clippy, test, test-cli

start: ## (Re)build and start native :8104 + exec :8105
	scripts/start-all.sh

start-adk: ## Start the Rust agents + adk api_server --a2a :8106
	scripts/start-adk.sh

stop: ## Stop the Rust agents and ADK
	scripts/stop-all.sh

test-cli: ## a2a CLI checks against both Rust agents
	scripts/test-cli.sh

test-adk: ## ADK checks (calls Gemini)
	scripts/test-adk.sh

tour: ## Record an a2a CLI tour to results/cli-tour-*.md
	scripts/cli-tour.sh

bench: ## Benchmark native + exec (MIN, MAX, REPS)
	MIN=$(MIN) MAX=$(MAX) REPS=$(REPS) scripts/bench.sh

bench-adk: ## Benchmark with the ADK series added (calls Gemini)
	ADK=1 MIN=$(MIN) MAX=$(MAX) REPS=$(REPS) scripts/bench.sh

cli-bench: ## Time the a2a CLI itself as a client (needs agents up)
	scripts/cli-bench.py --min $(MIN) --max $(MAX) --reps $(REPS)

cli-transport: ## a2a send wall time per transport, interleaved (needs agents up)
	scripts/cli-transport.py

adk-run: ## adk run, one shot with Q="...", else interactive
	scripts/adk-run.sh $(if $(Q),"$(Q)")

adk-web: ## adk web dev UI on :8107
	scripts/adk-web.sh

reliability: ## Repeated ADK checks, RUNS times (calls Gemini 2*RUNS)
	RUNS=$(RUNS) scripts/adk-reliability.sh

summarize: ## Aggregates the article quotes, from results/*.json
	scripts/summarize-results.py

clean: ## cargo clean and remove logs/
	cargo clean
	rm -rf logs
