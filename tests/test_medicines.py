import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("DYNAMODB_TABLE", "medsense-test-medicines")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")


@pytest.fixture
def client():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
        ddb.create_table(
            TableName=os.environ["DYNAMODB_TABLE"],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        from app.main import app

        yield TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_get_medicine(client):
    resp = client.post(
        "/api/medicines",
        json={"name": "Aspirin", "description": "Pain relief", "side_effects": ["nausea"]},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Aspirin"

    resp = client.get(f"/api/medicines/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Aspirin"


def test_search_medicines(client):
    client.post("/api/medicines", json={"name": "Paracetamol"})
    client.post("/api/medicines", json={"name": "Ibuprofen"})

    resp = client.get("/api/medicines", params={"search": "para"})
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert names == ["Paracetamol"]


def test_get_missing_medicine_404(client):
    resp = client.get("/api/medicines/does-not-exist")
    assert resp.status_code == 404
