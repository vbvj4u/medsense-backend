import os

import boto3
from moto import mock_aws

os.environ["AWS_REGION"] = "ap-southeast-2"


def test_get_secret_reads_and_decrypts_ssm_parameter():
    with mock_aws():
        ssm = boto3.client("ssm", region_name="ap-southeast-2")
        ssm.put_parameter(
            Name="/medsense/dev/medicine-api-key",
            Value="real-secret-value",
            Type="SecureString",
        )

        from app.secrets import get_secret

        get_secret.cache_clear()
        assert get_secret("/medsense/dev/medicine-api-key") == "real-secret-value"


def test_get_medicine_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("MEDICINE_API_KEY_PARAM", raising=False)

    from app.secrets import get_medicine_api_key

    assert get_medicine_api_key() is None
