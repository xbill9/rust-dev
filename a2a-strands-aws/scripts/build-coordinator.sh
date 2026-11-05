#!/bin/bash
# Build the arm64 coordinator image (AgentCore Runtime runs arm64 only) on any
# machine: pip fetches aarch64 wheels, Go cross-compiles the a2a CLI, and the
# Dockerfile only copies. Usage: scripts/build-coordinator.sh [tag]
# ARCH=amd64 builds the same image for x86_64, to smoke-test it locally.
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${1:-a2a-strands-coordinator:local}"
A2A_CLI_VERSION=v0.3.1
ARCH="${ARCH:-arm64}"
case $ARCH in arm64) PYARCH=aarch64 ;; amd64) PYARCH=x86_64 ;; *) echo "ARCH arm64|amd64"; exit 2 ;; esac
rm -rf build/coordinator && mkdir -p build/coordinator
python3 -m pip install -q --target build/coordinator/site \
  --platform manylinux_2_28_$PYARCH --platform manylinux2014_$PYARCH \
  --python-version 3.13 --implementation cp --only-binary=:all: \
  -r coordinator/requirements.txt
gomod=$(mktemp -d)
( cd "$gomod" && go mod init cross >/dev/null 2>&1 \
  && go get "github.com/a2aproject/a2a-cli@$A2A_CLI_VERSION" >/dev/null 2>&1 \
  && GOOS=linux GOARCH=$ARCH CGO_ENABLED=0 go build -trimpath \
       -o "$OLDPWD/build/coordinator/a2a" github.com/a2aproject/a2a-cli )
rm -rf "$gomod"
docker build --platform linux/$ARCH -f docker/coordinator.Dockerfile -t "$TAG" .
echo "built $TAG (linux/$ARCH)"
