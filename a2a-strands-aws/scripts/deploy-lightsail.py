#!/usr/bin/env python3
"""Deploy the Rust A2A agent to a Lightsail container service (nano, 1 node).

Creates the service if missing, builds docker/agent.Dockerfile, pushes it with
`aws lightsail push-container-image` (the only way into Lightsail's own
registry; needs the lightsailctl plugin), deploys it with ADVERTISE_URL set to
the service's public HTTPS URL, waits for RUNNING and records the URL in
.aws-state.json.

  scripts/deploy-lightsail.py            create/update
  scripts/deploy-lightsail.py --delete   delete the service
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).parent))
from aws_state import REGION, update  # noqa: E402

RIG = Path(__file__).resolve().parents[1]
SERVICE = "a2a-rust-mersenne"
CONTAINER = "agent"
LABEL = "agent"
PORT = 8080

ls = boto3.client("lightsail", region_name=REGION)


def service() -> dict | None:
    try:
        return ls.get_container_services(serviceName=SERVICE)["containerServices"][0]
    except ls.exceptions.NotFoundException:
        return None


def wait(pred, what: str, timeout: int = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = service()
        if s and pred(s):
            return s
        state = s and (s["state"], (s.get("currentDeployment") or {}).get("state"),
                       (s.get("nextDeployment") or {}).get("state"))
        print(f"  waiting for {what}: {state}", flush=True)
        time.sleep(15)
    sys.exit(f"timed out waiting for {what}")


def run(cmd: list[str]) -> str:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def deploy() -> None:
    if service() is None:
        print(f"creating container service {SERVICE} (nano, scale 1)")
        ls.create_container_service(serviceName=SERVICE, power="nano", scale=1)
    s = wait(lambda s: s["state"] in ("READY", "RUNNING"), "service READY")
    url = s["url"].rstrip("/")

    tag = f"{SERVICE}:local"
    run(["docker", "build", "--platform", "linux/amd64", "-f", "docker/agent.Dockerfile",
         "-t", tag, str(RIG)])
    out = run(["aws", "lightsail", "push-container-image", "--region", REGION,
               "--service-name", SERVICE, "--label", LABEL, "--image", tag])
    image = re.search(r'":' + re.escape(SERVICE) + r'\.' + LABEL + r'\.\d+"', out)
    if not image:
        sys.exit(f"no image name in push output:\n{out}")
    image = image.group(0).strip('"')
    print(f"pushed {image}")

    ls.create_container_service_deployment(
        serviceName=SERVICE,
        containers={CONTAINER: {
            "image": image,
            "environment": {"PORT": str(PORT), "HOST": "0.0.0.0", "ADVERTISE_URL": url},
            "ports": {str(PORT): "HTTP"},
        }},
        publicEndpoint={
            "containerName": CONTAINER,
            "containerPort": PORT,
            "healthCheck": {"path": "/.well-known/agent-card.json", "successCodes": "200",
                            "intervalSeconds": 10, "timeoutSeconds": 4,
                            "healthyThreshold": 2, "unhealthyThreshold": 3},
        },
    )
    wait(lambda s: s["state"] == "RUNNING" and not s.get("nextDeployment")
         and s["currentDeployment"]["containers"][CONTAINER]["image"] == image,
         "deployment ACTIVE")
    update(lightsail_service=SERVICE, lightsail_url=url, lightsail_image=image)
    print(f"✅ {url}/.well-known/agent-card.json")


def delete() -> None:
    if service():
        ls.delete_container_service(serviceName=SERVICE)
        print(f"deleted {SERVICE}")
    update(lightsail_service=None, lightsail_url=None, lightsail_image=None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    delete() if ap.parse_args().delete else deploy()
