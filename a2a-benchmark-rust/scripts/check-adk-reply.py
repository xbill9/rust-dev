#!/usr/bin/env python3
"""Check an ADK benchmark reply (`a2a send -o json` output) against its tool call.

Usage: check-adk-reply.py reply.json MIN MAX REPS

Fails unless the model called run_benchmark exactly once with the requested
arguments, and every number in its final text is a value the tool returned
(or one of the arguments). Checking the call matters as much as the numbers:
a wrong argument yields exact, well-formatted figures for the wrong question.
"""
import json
import re
import sys


def numbers(v, out):
    if isinstance(v, bool):
        return
    if isinstance(v, (int, float)):
        out.add(float(v))
    elif isinstance(v, dict):
        for x in v.values():
            numbers(x, out)
    elif isinstance(v, list):
        for x in v:
            numbers(x, out)


def main():
    path, want = sys.argv[1], dict(zip(("min_n", "max_n", "reps"), map(int, sys.argv[2:5])))
    task = json.load(open(path))["task"]
    calls, responses, texts = [], [], []
    for m in task.get("history", []):
        for p in m["parts"]:
            d = p.get("data")
            if isinstance(d, dict) and d.get("name") == "run_benchmark":
                (responses if "response" in d else calls).append(d)
            elif m["role"] == "ROLE_AGENT" and "text" in p:
                texts.append(p["text"])
    ok = True
    print(f"state: {task['status']['state']}")
    print(f"run_benchmark calls: {len(calls)}")
    if len(calls) != 1 or len(responses) != 1:
        print("FAIL: expected exactly one run_benchmark call and response")
        return 1
    args = {k: int(v) for k, v in calls[0].get("args", {}).items()}
    print(f"args sent: {args}  requested: {want}")
    if args != want:
        print("FAIL: model sent different arguments than requested")
        ok = False
    allowed = set()
    numbers(responses[0]["response"], allowed)
    allowed |= {float(v) for v in want.values()}
    reply = texts[-1] if texts else ""
    quoted = [t for t in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", reply)]
    unmatched = sorted({q for q in quoted if float(q) not in allowed}, key=float)
    print(f"numbers in reply: {len(quoted)}  not from the tool: {len(unmatched)}")
    if unmatched:
        print("FAIL: unmatched numbers:", ", ".join(unmatched[:20]))
        ok = False
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
