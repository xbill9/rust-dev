#!/usr/bin/env python3
"""Print a Cognito access token for the a2a CLI: a2a --auth "Bearer $(scripts/cognito-token.py)" ...

Uses the user that scripts/deploy-agentcore.py created (ids and password in
.aws-state.json). Tokens last one hour.
"""

from __future__ import annotations

import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).parent))
from aws_state import REGION, load  # noqa: E402

s = load()
if "cognito_client_id" not in s:
    sys.exit("no Cognito client in .aws-state.json: run scripts/deploy-agentcore.py first")
r = boto3.client("cognito-idp", region_name=REGION).initiate_auth(
    ClientId=s["cognito_client_id"],
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": s["cognito_user"], "PASSWORD": s["cognito_password"]},
)
print(r["AuthenticationResult"]["AccessToken"])
