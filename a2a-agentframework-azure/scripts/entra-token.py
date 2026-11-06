#!/usr/bin/env python3
"""Print an Entra ID access token for the coordinator: a2a --auth "Bearer $(scripts/entra-token.py)" ...

The token is for the coordinator's app registration (api://<app id>, created
by scripts/deploy-coordinator.py), issued to the Azure CLI as the signed-in
user. deploy-coordinator.py pre-authorizes the Azure CLI on that app, so no
consent prompt is needed. Tokens last about an hour.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import az, load  # noqa: E402

s = load()
if "coordinator_app_id" not in s:
    sys.exit("no coordinator app registration in .azure-state.json: run scripts/deploy-coordinator.py first")
print(az("account", "get-access-token", "--resource", f"api://{s['coordinator_app_id']}",
         quiet=True)["accessToken"])
