#!/usr/bin/env python3
"""Deploy the Rust A2A agent to Azure Container Apps (0.25 vCPU, 0.5 GiB, 1 replica).

Builds docker/agent.Dockerfile locally, pushes it to the rig's container
registry, and creates or updates the container app. The app pulls with the
rig's user-assigned identity (AcrPull, no registry password) and sets
ADVERTISE_URL to its public HTTPS URL, so the card's interfaces point at
Container Apps. Records the URL in .azure-state.json.

  scripts/deploy-rust.py            create/update
  scripts/deploy-rust.py --delete   delete the container app
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_state import ENV, RG, RUST_APP, az, build_image, ensure_base, load, update  # noqa: E402

PORT = 8080


def app_url(name: str) -> str:
    domain = az("containerapp", "env", "show", "-n", ENV, "-g", RG, quiet=True)["properties"]["defaultDomain"]
    return f"https://{name}.{domain}"


def create_or_update(name: str, image: str, env: dict[str, str], port: int) -> None:
    """Shared by deploy-coordinator.py."""
    s = load()
    env_args = [f"{k}={v}" for k, v in env.items()]
    if az("containerapp", "show", "-n", name, "-g", RG, check=False, quiet=True) is None:
        az("containerapp", "create", "-n", name, "-g", RG, "--environment", ENV,
           "--image", image, "--target-port", str(port), "--ingress", "external",
           "--user-assigned", s["identity_id"],
           "--registry-server", s["acr_login_server"], "--registry-identity", s["identity_id"],
           "--cpu", "0.25", "--memory", "0.5Gi", "--min-replicas", "1", "--max-replicas", "1",
           "--env-vars", *env_args)
    else:
        az("containerapp", "update", "-n", name, "-g", RG, "--image", image,
           "--set-env-vars", *env_args)
    wait_revision(name, image)


def wait_revision(name: str, image: str, timeout: int = 600) -> None:
    """Wait until the revision running `image` is ready and no other revision
    still has replicas: an old revision keeps answering while it deprovisions."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        revs = az("containerapp", "revision", "list", "-n", name, "-g", RG, quiet=True) or []
        new = [r for r in revs if r["properties"]["template"]["containers"][0]["image"] == image]
        old_live = [r["name"] for r in revs if r not in new and r["properties"].get("active")
                    and r["properties"].get("runningState") not in ("Deprovisioned", "Stopped")]
        state = new[0]["properties"].get("runningState") if new else None
        if new and state in ("Running", "RunningAtMaxScale") and not old_live:
            return
        print(f"  waiting for revision: new={state} old still live={old_live}", flush=True)
        time.sleep(10)
    sys.exit(f"timed out waiting for {name} to run only {image}")


def wait_card(url: str, headers: dict | None = None, ok=(200,), timeout: int = 300) -> int:
    t0 = time.time()
    code = None
    while time.time() - t0 < timeout:
        req = urllib.request.Request(f"{url}/.well-known/agent-card.json", headers=headers or {})
        try:
            code = urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e:
            code = e.code
        except OSError as e:
            code = str(e)
        if code in ok:
            return code
        print(f"  waiting for {url}: {code}", flush=True)
        time.sleep(10)
    sys.exit(f"timed out waiting for {url} (last: {code})")


def deploy() -> None:
    ensure_base()
    url = app_url(RUST_APP)
    image = build_image("docker/agent.Dockerfile", "mersenne-agent")
    create_or_update(RUST_APP, image, {"PORT": str(PORT), "HOST": "0.0.0.0", "ADVERTISE_URL": url}, PORT)
    wait_card(url)
    update(rust_app=RUST_APP, rust_url=url, rust_image=image)
    print(f"✅ {url}/.well-known/agent-card.json")


def delete() -> None:
    if az("containerapp", "show", "-n", RUST_APP, "-g", RG, check=False, quiet=True):
        az("containerapp", "delete", "-n", RUST_APP, "-g", RG, "--yes")
    update(rust_app=None, rust_url=None, rust_image=None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    delete() if ap.parse_args().delete else deploy()
