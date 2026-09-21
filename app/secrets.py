"""
Runtime secret access.

Secrets (API keys, DB passwords) are never baked into Lambda
environment variables as plaintext - Terraform (medsense-infra) writes
them to SSM Parameter Store as SecureString values, grants this
function's role `ssm:GetParameter` on just those parameters, and
passes only the *parameter name* in as an env var (e.g.
MEDICINE_API_KEY_PARAM). This module resolves that name to the actual
secret value at call time, with a per-container cache so a warm Lambda
doesn't call SSM on every request.
"""
import os
from functools import lru_cache

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")

_ssm = None


def _client():
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm", region_name=AWS_REGION)
    return _ssm


@lru_cache(maxsize=8)
def get_secret(parameter_name: str) -> str:
    """Fetch and decrypt an SSM SecureString parameter by name, cached
    for the lifetime of this Lambda execution environment."""
    response = _client().get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


def get_medicine_api_key() -> str | None:
    param_name = os.environ.get("MEDICINE_API_KEY_PARAM")
    if not param_name:
        return None
    return get_secret(param_name)
