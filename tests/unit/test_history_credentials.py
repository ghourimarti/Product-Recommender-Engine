"""DynamoDB credential selection: dummy keys only for the local emulator.

Before this, the history store always passed dummy "local" credentials when none were set. On EKS
that overrides the pod's IAM role (IRSA / Pod Identity), so every call to the real table would
have been rejected.
"""

from __future__ import annotations

from core.config import Settings
from core.history import dynamodb_resource_kwargs


def _settings(endpoint: str = "", key: str = "", secret: str = "") -> Settings:
    # model_construct skips .env and the process environment, so the test is hermetic.
    return Settings.model_construct(
        dynamodb_endpoint=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        aws_region="us-east-1",
    )


def test_local_emulator_gets_dummy_credentials() -> None:
    kwargs = dynamodb_resource_kwargs(_settings(endpoint="http://dynamodb:8000"))
    assert kwargs["endpoint_url"] == "http://dynamodb:8000"
    assert kwargs["aws_access_key_id"] == "local"
    assert kwargs["aws_secret_access_key"] == "local"


def test_real_aws_without_keys_leaves_credentials_to_the_default_chain() -> None:
    # EKS with IRSA or Pod Identity: boto3 must find the pod's role itself.
    assert dynamodb_resource_kwargs(_settings()) == {"region_name": "us-east-1"}


def test_real_aws_with_explicit_keys_passes_them() -> None:
    # e.g. DOKS reaching AWS DynamoDB with a table-scoped IAM user (todo 7.0.5a).
    kwargs = dynamodb_resource_kwargs(_settings(key="test-access-key", secret="test-secret"))
    assert "endpoint_url" not in kwargs
    assert kwargs["aws_access_key_id"] == "test-access-key"
    assert kwargs["aws_secret_access_key"] == "test-secret"
