#!/usr/bin/env python3
"""Ids of the AWS resources this rig creates, kept in .aws-state.json (gitignored).

  scripts/aws_state.py get lightsail_url
  scripts/aws_state.py show
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / ".aws-state.json"
REGION = "us-east-1"


def load() -> dict:
    return json.loads(PATH.read_text()) if PATH.exists() else {}


def update(**kv) -> dict:
    s = load()
    for k, v in kv.items():
        if v is None:
            s.pop(k, None)
        else:
            s[k] = v
    PATH.write_text(json.dumps(s, indent=2) + "\n")
    PATH.chmod(0o600)
    return s


if __name__ == "__main__":
    s = load()
    if len(sys.argv) == 3 and sys.argv[1] == "get":
        if sys.argv[2] not in s:
            sys.exit(f"{sys.argv[2]} not in {PATH.name}: run the deploy script first")
        print(s[sys.argv[2]])
    elif sys.argv[1:] == ["show"]:
        print(json.dumps({k: v for k, v in s.items() if "password" not in k}, indent=2))
    else:
        sys.exit(__doc__)
