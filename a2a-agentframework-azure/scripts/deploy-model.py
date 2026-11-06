#!/usr/bin/env python3
"""Create the Azure OpenAI model the coordinator uses (local and in the cloud).

An AIServices account with a custom subdomain (needed for Entra ID auth), one
model deployment, and "Cognitive Services OpenAI User" for both the signed-in
user (local runs, through `az login`) and the rig's managed identity (the
coordinator container). No API keys are used anywhere.

  scripts/deploy-model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import (  # noqa: E402
    LOCATION, MODEL, MODEL_CAPACITY, MODEL_SKU, MODEL_VERSION, RG,
    assign_role, az, ensure_base, openai_name, update,
)

ROLE = "Cognitive Services OpenAI User"


def main() -> None:
    s = ensure_base()
    name = openai_name()
    acct = az("cognitiveservices", "account", "show", "-n", name, "-g", RG, check=False, quiet=True)
    if acct is None:
        acct = az("cognitiveservices", "account", "create", "-n", name, "-g", RG, "-l", LOCATION,
                  "--kind", "AIServices", "--sku", "S0", "--custom-domain", name, "--yes")
    if az("cognitiveservices", "account", "deployment", "show", "-n", name, "-g", RG,
          "--deployment-name", MODEL, check=False, quiet=True) is None:
        az("cognitiveservices", "account", "deployment", "create", "-n", name, "-g", RG,
           "--deployment-name", MODEL, "--model-name", MODEL, "--model-version", MODEL_VERSION,
           "--model-format", "OpenAI", "--sku-name", MODEL_SKU, "--sku-capacity", str(MODEL_CAPACITY))
    me = az("ad", "signed-in-user", "show", quiet=True)["id"]
    assign_role(me, ROLE, acct["id"], ptype="User")
    assign_role(s["identity_principal_id"], ROLE, acct["id"])
    endpoint = acct["properties"]["endpoint"]
    update(openai_account=name, openai_endpoint=endpoint, model=MODEL)
    print(f"✅ {endpoint} deployment {MODEL}")


if __name__ == "__main__":
    main()
