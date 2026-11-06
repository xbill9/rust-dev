#!/usr/bin/env python3
"""Delete every Azure resource the rig created: the coordinator's app
registration (it lives in Entra ID, outside the resource group), then the
whole resource group. Clears .azure-state.json.

  scripts/teardown.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import PATH, RG, az, load  # noqa: E402

s = load()
if "coordinator_app_id" in s:
    az("ad", "app", "delete", "--id", s["coordinator_app_id"], check=False)
if az("group", "exists", "-n", RG, quiet=True):
    az("group", "delete", "-n", RG, "--yes")
# A deleted AIServices account is soft-deleted; purge it so the name is free.
if "openai_account" in s:
    az("cognitiveservices", "account", "purge", "-n", s["openai_account"], "-g", RG,
       "-l", s.get("location", "eastus2"), check=False)
PATH.unlink(missing_ok=True)
print(f"deleted {RG}")
