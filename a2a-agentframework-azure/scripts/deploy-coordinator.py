#!/usr/bin/env python3
"""Deploy the Agent Framework coordinator to Azure Container Apps behind Entra ID.

1. An Entra ID app registration for the coordinator: identifier URI
   api://<app id>, one delegated scope (`access_as_user`), v2 access tokens,
   and the Azure CLI pre-authorized, so `az account get-access-token
   --resource api://<app id>` returns a token with no consent prompt.
2. docker/coordinator.Dockerfile, built locally and pushed to the rig's registry.
3. The container app: RUST_AGENT_URL is the Container Apps Rust agent, the
   model is reached with the rig's managed identity (AZURE_CLIENT_ID).
4. Container Apps built-in authentication with the Microsoft provider:
   requests without a valid bearer token for the app registration get 401,
   the card included.

Run scripts/deploy-model.py and scripts/deploy-rust.py first.

  scripts/deploy-coordinator.py            create/update
  scripts/deploy-coordinator.py --delete   delete the app and the app registration
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import (  # noqa: E402
    AZ_CLI_CLIENT_ID, COORD_APP, RG, az, build_image, ensure_base, load, update,
)
from importlib import import_module  # noqa: E402

rust = import_module("deploy-rust")
PORT = 8080
GRAPH = "https://graph.microsoft.com/v1.0"


def graph_patch(object_id: str, body: dict) -> None:
    az("rest", "--method", "PATCH", "--uri", f"{GRAPH}/applications/{object_id}",
       "--headers", "Content-Type=application/json", "--body", json.dumps(body))


def app_registration() -> tuple[str, str]:
    s = load()
    app = None
    if "coordinator_app_id" in s:
        app = az("ad", "app", "show", "--id", s["coordinator_app_id"], check=False, quiet=True)
    if app is None:
        app = az("ad", "app", "create", "--display-name", COORD_APP, "--sign-in-audience", "AzureADMyOrg")
    app_id, object_id = app["appId"], app["id"]
    update(coordinator_app_id=app_id, coordinator_app_object_id=object_id)
    scopes = (app.get("api") or {}).get("oauth2PermissionScopes") or []
    scope_id = scopes[0]["id"] if scopes else str(uuid.uuid4())
    if not scopes:
        graph_patch(object_id, {
            "identifierUris": [f"api://{app_id}"],
            "api": {"requestedAccessTokenVersion": 2, "oauth2PermissionScopes": [{
                "id": scope_id, "value": "access_as_user", "type": "User", "isEnabled": True,
                "adminConsentDisplayName": "Call the A2A coordinator",
                "adminConsentDescription": "Send A2A requests to the Agent Framework coordinator.",
                "userConsentDisplayName": "Call the A2A coordinator",
                "userConsentDescription": "Send A2A requests to the Agent Framework coordinator.",
            }]},
        })
    graph_patch(object_id, {"api": {"preAuthorizedApplications": [
        {"appId": AZ_CLI_CLIENT_ID, "delegatedPermissionIds": [scope_id]},
    ]}})
    if az("ad", "sp", "show", "--id", app_id, check=False, quiet=True) is None:
        az("ad", "sp", "create", "--id", app_id)
    return app_id, az("account", "show", quiet=True)["tenantId"]


def deploy() -> None:
    s = ensure_base()
    for k, script in (("openai_endpoint", "deploy-model.py"), ("rust_url", "deploy-rust.py")):
        if k not in s:
            sys.exit(f"{k} missing from .azure-state.json: run scripts/{script} first")
    app_id, tenant = app_registration()
    url = rust.app_url(COORD_APP)
    image = build_image("docker/coordinator.Dockerfile", "af-coordinator")
    rust.create_or_update(COORD_APP, image, {
        "PORT": str(PORT), "ADVERTISE_URL": url, "RUST_AGENT_URL": s["rust_url"],
        "AZURE_OPENAI_ENDPOINT": s["openai_endpoint"], "MODEL": s["model"],
        "AZURE_CLIENT_ID": s["identity_client_id"],
    }, PORT)
    az("containerapp", "auth", "microsoft", "update", "-n", COORD_APP, "-g", RG,
       "--client-id", app_id,
       "--issuer", f"https://login.microsoftonline.com/{tenant}/v2.0",
       "--allowed-audiences", f"api://{app_id},{app_id}", "--yes")
    az("containerapp", "auth", "update", "-n", COORD_APP, "-g", RG,
       "--enabled", "true", "--unauthenticated-client-action", "Return401")
    rust.wait_card(url, ok=(401,))
    update(coordinator_app=COORD_APP, coordinator_url=url, coordinator_image=image)
    print(f"✅ {url}/.well-known/agent-card.json (401 without a token)")


def delete() -> None:
    s = load()
    if az("containerapp", "show", "-n", COORD_APP, "-g", RG, check=False, quiet=True):
        az("containerapp", "delete", "-n", COORD_APP, "-g", RG, "--yes")
    if "coordinator_app_id" in s:
        az("ad", "app", "delete", "--id", s["coordinator_app_id"], check=False)
    update(coordinator_app=None, coordinator_url=None, coordinator_image=None,
           coordinator_app_id=None, coordinator_app_object_id=None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    delete() if ap.parse_args().delete else deploy()
