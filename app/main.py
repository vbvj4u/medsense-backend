"""
MedSense backend API (Application tier).

FastAPI app wrapped with Mangum so it runs unchanged on AWS Lambda
behind API Gateway (see app.handler below), while `uvicorn app.main:app`
still works for local development.

Data tier: DynamoDB single-table, partition key `id`.
"""
import os
import uuid
from typing import Optional

import boto3
from fastapi import FastAPI, HTTPException, Query
from mangum import Mangum
from pydantic import BaseModel, Field

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "medsense-dev-medicines")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")

app = FastAPI(title="MedSense API", version="1.0.0")

_dynamodb = None


def get_table():
    """Lazy DynamoDB resource so unit tests can run without AWS creds."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamodb.Table(TABLE_NAME)


class Medicine(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Generic and/or brand name, e.g. 'Amoxicillin'")
    description: Optional[str] = Field(None, description="What the medicine is used for")
    dosage_instructions: Optional[str] = Field(None, description="Standard usage rules")
    side_effects: list[str] = Field(default_factory=list)


@app.get("/health")
def health():
    return {"status": "ok", "environment": ENVIRONMENT}


@app.get("/api/medicines", response_model=list[Medicine])
def search_medicines(search: Optional[str] = Query(None, description="Medicine name to search for")):
    table = get_table()
    if search:
        # Table is small (dev/demo scale); a filtered scan is fine here.
        # Swap for a GSI + query if this ever needs to scale past a few
        # thousand items.
        response = table.scan()
        items = [
            item for item in response.get("Items", [])
            if search.lower() in item.get("name", "").lower()
        ]
    else:
        response = table.scan()
        items = response.get("Items", [])
    return items


@app.get("/api/medicines/{medicine_id}", response_model=Medicine)
def get_medicine(medicine_id: str):
    table = get_table()
    response = table.get_item(Key={"id": medicine_id})
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return item


@app.post("/api/medicines", response_model=Medicine, status_code=201)
def create_medicine(medicine: Medicine):
    table = get_table()
    medicine.id = medicine.id or str(uuid.uuid4())
    table.put_item(Item=medicine.model_dump())
    return medicine


# AWS Lambda entrypoint - referenced as `app.handler` by
# medsense-infra's lambda_backend module.
handler = Mangum(app)
