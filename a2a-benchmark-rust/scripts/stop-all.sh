#!/bin/bash
pkill -f target/release/mersenne-agent || true
pkill -f "a2a server --exec .*mersenne-exec" || true
