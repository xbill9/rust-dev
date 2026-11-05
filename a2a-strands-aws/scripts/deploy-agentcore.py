#!/usr/bin/env python3
"""Deploy the Strands coordinator to Amazon Bedrock AgentCore Runtime (A2A).

  scripts/deploy-agentcore.py            create/update everything below
  scripts/deploy-agentcore.py --delete   delete everything below

Resources (us-east-1, all named a2a-strands-*):
  * ECR repository a2a-strands-coordinator, image built by build-coordinator.sh
  * IAM role a2a-strands-coordinator-runtime: ECR pull, CloudWatch Logs,
    bedrock:InvokeModel*
  * Cognito user pool a2a-strands-aws with public app client a2a-cli and one
    user, so the a2a CLI can send `--auth "Bearer <token>"` (scripts/cognito-token.py)
  * AgentCore runtime a2a_strands_coordinator: serverProtocol A2A, inbound
    CUSTOM_JWT (the Cognito pool), PUBLIC network, RUST_AGENT_URL = the
    Lightsail agent from .aws-state.json unless --rust-agent-url is given
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent))
from aws_state import REGION, load, update  # noqa: E402

RIG = Path(__file__).resolve().parents[1]
REPO = "a2a-strands-coordinator"
ROLE = "a2a-strands-coordinator-runtime"
POOL = "a2a-strands-aws"
CLIENT = "a2a-cli"
USER = "a2a-cli"
RUNTIME = "a2a_strands_coordinator"
MODEL_ID = "us.anthropic.claude-haiku-5-5"

sess = boto3.Session(region_name=REGION)
account = sess.client("sts").get_caller_identity()["Account"]
ecr = sess.client("ecr")
iam = sess.client("iam")
cog = sess.client("cognito-idp")
ac = sess.client("bedrock-agentcore-control")


def sh(cmd: list[str], **kw) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def push_image() -> str:
    try:
        uri = ecr.describe_repositories(repositoryNames=[REPO])["repositories"][0]["repositoryUri"]
    except ecr.exceptions.RepositoryNotFoundException:
        uri = ecr.create_repository(repositoryName=REPO)["repository"]["repositoryUri"]
    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    image = f"{uri}:{tag}"
    sh([str(RIG / "scripts/build-coordinator.sh"), image])
    auth = ecr.get_authorization_token()["authorizationData"][0]
    user, password = base64.b64decode(auth["authorizationToken"]).decode().split(":", 1)
    sh(["docker", "login", "--username", user, "--password-stdin", auth["proxyEndpoint"]],
       input=password.encode())
    sh(["docker", "push", image])
    return image


def ensure_role() -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": account},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{account}:*"},
            },
        }],
    }
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
             "Resource": f"arn:aws:ecr:{REGION}:{account}:repository/{REPO}"},
            {"Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*"},
            {"Effect": "Allow",
             "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                        "logs:DescribeLogStreams", "logs:DescribeLogGroups"],
             "Resource": f"arn:aws:logs:{REGION}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"},
            {"Effect": "Allow",
             "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
             "Resource": ["arn:aws:bedrock:*::foundation-model/*",
                          f"arn:aws:bedrock:*:{account}:inference-profile/*"]},
        ],
    }
    try:
        arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
        iam.update_assume_role_policy(RoleName=ROLE, PolicyDocument=json.dumps(trust))
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust),
                              Description="AgentCore Runtime role for the a2a-strands-aws rig")["Role"]["Arn"]
    iam.put_role_policy(RoleName=ROLE, PolicyName="runtime", PolicyDocument=json.dumps(policy))
    return arn


def ensure_cognito() -> dict:
    s = load()
    pools = [p for p in cog.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == POOL]
    pool_id = pools[0]["Id"] if pools else cog.create_user_pool(
        PoolName=POOL, Policies={"PasswordPolicy": {"MinimumLength": 16}})["UserPool"]["Id"]
    clients = [c for c in cog.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)["UserPoolClients"]
               if c["ClientName"] == CLIENT]
    client_id = clients[0]["ClientId"] if clients else cog.create_user_pool_client(
        UserPoolId=pool_id, ClientName=CLIENT, GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )["UserPoolClient"]["ClientId"]
    password = s.get("cognito_password") if s.get("cognito_pool_id") == pool_id else None
    if not password:
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(24)) + "Aa1!"
        try:
            cog.admin_create_user(UserPoolId=pool_id, Username=USER, MessageAction="SUPPRESS")
        except cog.exceptions.UsernameExistsException:
            pass
        cog.admin_set_user_password(UserPoolId=pool_id, Username=USER, Password=password, Permanent=True)
    update(cognito_pool_id=pool_id, cognito_client_id=client_id, cognito_user=USER,
           cognito_password=password)
    return {"pool_id": pool_id, "client_id": client_id}


def find_runtime() -> dict | None:
    for r in ac.list_agent_runtimes()["agentRuntimes"]:
        if r["agentRuntimeName"] == RUNTIME:
            return r
    return None


def wait_ready(runtime_id: str) -> dict:
    for _ in range(80):
        r = ac.get_agent_runtime(agentRuntimeId=runtime_id)
        print(f"  runtime {r['status']} (version {r['agentRuntimeVersion']})", flush=True)
        if r["status"] == "READY":
            return r
        if r["status"].endswith("FAILED"):
            sys.exit(f"runtime failed: {r.get('failureReason', r['status'])}")
        time.sleep(10)
    sys.exit("timed out waiting for runtime READY")


def deploy(rust_agent_url: str | None) -> None:
    rust = rust_agent_url or load().get("lightsail_url")
    if not rust:
        sys.exit("no Rust agent URL: run scripts/deploy-lightsail.py or pass --rust-agent-url")
    image = push_image()
    role_arn = ensure_role()
    c = ensure_cognito()
    spec = dict(
        agentRuntimeArtifact={"containerConfiguration": {"containerUri": image}},
        roleArn=role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
        protocolConfiguration={"serverProtocol": "A2A"},
        authorizerConfiguration={"customJWTAuthorizer": {
            "discoveryUrl": f"https://cognito-idp.{REGION}.amazonaws.com/{c['pool_id']}/.well-known/openid-configuration",
            "allowedClients": [c["client_id"]],
        }},
        description="Strands coordinator (Bedrock) for the Rust Mersenne A2A agent",
    )
    env = {"RUST_AGENT_URL": rust, "MODEL_ID": MODEL_ID}
    existing = find_runtime()
    if existing is None:
        for attempt in range(12):  # a new IAM role takes a few seconds to be assumable
            try:
                existing = ac.create_agent_runtime(agentRuntimeName=RUNTIME, environmentVariables=env, **spec)
                break
            except ClientError as e:
                if e.response["Error"]["Code"] != "ValidationException" or attempt == 11:
                    raise
                print(f"  retrying create: {e.response['Error']['Message'][:120]}", flush=True)
                time.sleep(10)
    runtime_id, arn = existing["agentRuntimeId"], existing["agentRuntimeArn"]
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{quote(arn, safe='')}/invocations/"
    wait_ready(runtime_id)
    # The card must advertise the AgentCore URL, which exists only once the
    # runtime does: set it (and the new image, on a redeploy) in an update.
    ac.update_agent_runtime(agentRuntimeId=runtime_id,
                            environmentVariables={**env, "AGENTCORE_RUNTIME_URL": url}, **spec)
    r = wait_ready(runtime_id)
    # The a2a CLI treats a URL without a card path as an origin and asks
    # https://bedrock-agentcore.<region>.amazonaws.com/.well-known/... (404):
    # hand it the full card URL.
    update(agentcore_runtime_id=runtime_id, agentcore_arn=arn, agentcore_url=url,
           agentcore_card=url + ".well-known/agent-card.json",
           agentcore_image=image, agentcore_version=r["agentRuntimeVersion"],
           agentcore_rust_agent_url=rust)
    print(f"✅ {url}")


def delete() -> None:
    r = find_runtime()
    if r:
        ac.delete_agent_runtime(agentRuntimeId=r["agentRuntimeId"])
        print(f"deleted runtime {RUNTIME}")
    s = load()
    if s.get("cognito_pool_id"):
        try:
            cog.delete_user_pool(UserPoolId=s["cognito_pool_id"])
            print(f"deleted user pool {POOL}")
        except cog.exceptions.ResourceNotFoundException:
            pass
    try:
        iam.delete_role_policy(RoleName=ROLE, PolicyName="runtime")
        iam.delete_role(RoleName=ROLE)
        print(f"deleted role {ROLE}")
    except iam.exceptions.NoSuchEntityException:
        pass
    try:
        ecr.delete_repository(repositoryName=REPO, force=True)
        print(f"deleted ECR repository {REPO}")
    except ecr.exceptions.RepositoryNotFoundException:
        pass
    update(**{k: None for k in load() if k.startswith(("agentcore_", "cognito_"))})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--rust-agent-url")
    a = ap.parse_args()
    delete() if a.delete else deploy(a.rust_agent_url)
