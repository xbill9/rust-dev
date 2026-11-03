---
name: bench
description: Run the native vs exec Mersenne A2A benchmark from fresh agents and report the results file. Arguments are REPS (default 10) and optional MAX.
disable-model-invocation: true
---

Run the benchmark with `$ARGUMENTS` (first value is REPS, default 10; second, if given, is MAX, default 22).

1. `scripts/stop-all.sh` so both agents restart on the current build (`start-all.sh` keeps already-running agents).
2. `REPS=<reps> MAX=<max> scripts/bench.sh`. It rebuilds in release, starts the agents, and writes `results/bench-<UTC stamp>.json` and `.md`.
3. Report from the new `results/bench-*.json` / `.md` only. Quote the figures `mersenne-bench` computed; do not compute means, ratios or rankings yourself. If a comparison is needed that the file does not contain, say so instead of calculating it.
4. Note the rep count with the numbers; the README warns 5 reps is noisy.
5. Do not commit the results unless asked.
