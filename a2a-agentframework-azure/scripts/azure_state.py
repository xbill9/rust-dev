#!/usr/bin/env python3
"""Names and ids of the Azure resources this rig creates.

Ids and URLs are kept in .azure-state.json (gitignored). Every resource lives
in one resource group, so `scripts/teardown.py` deletes them all at once.

  scripts/azure_state.py get rust_url
  scripts/azure_state.py show
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / ".azure-state.json"
LOCATION = "eastus2"
RG = "a2a-agentframework-azure-rg"
ENV = "a2a-af-env"
IDENTITY = "a2a-af-identity"
RUST_APP = "a2a-rust-mersenne"
COORD_APP = "a2a-af-coordinator"
MODEL = "gpt-5.4-mini"
MODEL_VERSION = "2026-03-17"
MODEL_SKU = "GlobalStandard"
MODEL_CAPACITY = 50  # thousands of tokens per minute
# Azure CLI's public client id: pre-authorized on the coordinator's app
# registration so `az account get-access-token --resource api://<app>` works.
AZ_CLI_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


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


def az(*args: str, check: bool = True, quiet: bool = False):
    """Run `az ... -o json` and return the parsed output (None when empty)."""
    cmd = ["az", *args, "-o", "json"]
    if not quiet:
        print("$ az", " ".join(args), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        if check:
            sys.exit(f"az {' '.join(args)} failed:\n{p.stderr.strip()}")
        return None
    if not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:  # a few commands (acr login) print plain text
        return p.stdout.strip()


def subscription() -> dict:
    return az("account", "show", quiet=True)


def suffix() -> str:
    """Short, stable per-subscription suffix for globally unique names."""
    return hashlib.sha256(subscription()["id"].encode()).hexdigest()[:6]


def acr_name() -> str:
    return f"a2aafazure{suffix()}"


def openai_name() -> str:
    return f"a2a-af-openai-{suffix()}"


def ensure_base() -> dict:
    """Resource group, registry, identity and Container Apps environment."""
    s = load()
    if s.get("base_ready"):
        return s
    az("group", "create", "-n", RG, "-l", LOCATION)
    acr = acr_name()
    if az("acr", "show", "-n", acr, "-g", RG, check=False, quiet=True) is None:
        az("acr", "create", "-n", acr, "-g", RG, "-l", LOCATION, "--sku", "Basic")
    login_server = az("acr", "show", "-n", acr, "-g", RG, quiet=True)["loginServer"]
    ident = az("identity", "show", "-n", IDENTITY, "-g", RG, check=False, quiet=True) \
        or az("identity", "create", "-n", IDENTITY, "-g", RG, "-l", LOCATION)
    acr_id = az("acr", "show", "-n", acr, "-g", RG, quiet=True)["id"]
    assign_role(ident["principalId"], "AcrPull", acr_id)
    if az("containerapp", "env", "show", "-n", ENV, "-g", RG, check=False, quiet=True) is None:
        az("containerapp", "env", "create", "-n", ENV, "-g", RG, "-l", LOCATION,
           "--logs-destination", "none")
    return update(
        resource_group=RG, location=LOCATION, acr=acr, acr_login_server=login_server,
        identity_id=ident["id"], identity_client_id=ident["clientId"],
        identity_principal_id=ident["principalId"], base_ready=True,
    )


def assign_role(principal_id: str, role: str, scope: str, ptype: str = "ServicePrincipal") -> None:
    have = az("role", "assignment", "list", "--assignee", principal_id, "--role", role,
              "--scope", scope, check=False, quiet=True)
    if have:
        return
    # A new identity can take a minute to reach Entra ID.
    for _ in range(12):
        if az("role", "assignment", "create", "--assignee-object-id", principal_id,
              "--assignee-principal-type", ptype, "--role", role, "--scope", scope,
              check=False) is not None:
            return
        time.sleep(10)
    sys.exit(f"could not assign {role} to {principal_id}")


def build_image(dockerfile: str, repo: str) -> str:
    """docker build locally (linux/amd64), push to the rig's ACR, return the image ref."""
    s = load()
    rig = Path(__file__).resolve().parents[1]
    tag = f"{s['acr_login_server']}/{repo}:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    az("acr", "login", "-n", s["acr"])
    for cmd in (["docker", "build", "--platform", "linux/amd64", "-f", dockerfile, "-t", tag, str(rig)],
                ["docker", "push", tag]):
        print("$", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, cwd=rig)
    return tag


if __name__ == "__main__":
    s = load()
    if len(sys.argv) == 3 and sys.argv[1] == "get":
        if sys.argv[2] not in s:
            sys.exit(f"{sys.argv[2]} not in {PATH.name}: run the deploy script first")
        print(s[sys.argv[2]])
    elif sys.argv[1:] == ["show"]:
        print(json.dumps(s, indent=2))
    else:
        sys.exit(__doc__)
