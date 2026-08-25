import os
import time
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from mangum import Mangum

# Behind API Gateway the app is served under a stage prefix (e.g. /Prod), so the
# links FastAPI generates for /docs must include it. SAM sets ROOT_PATH in the
# cloud; locally it's empty, so uvicorn keeps serving everything from /.
app = FastAPI(title="Feedback API", root_path=os.environ.get("ROOT_PATH", ""))

# DynamoDB table name is passed in as an environment variable by SAM.
TABLE_NAME = os.environ.get("TABLE_NAME", "FeedbackTable")

_table = None


def get_table():
    """Return the DynamoDB table, creating the client on first use.

    boto3 automatically uses the Lambda execution role's credentials in AWS,
    and your local AWS CLI credentials when running locally. Building the
    client lazily (instead of at import time) means the app still starts when
    no credentials or region are configured — so the health endpoint works
    even in the plain Docker container of Phase 2.
    """
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


class FeedbackIn(BaseModel):
    # extra="allow" keeps any field the client sends beyond the two declared
    # below. Pydantic's default is to silently discard them; this makes the
    # endpoint accept arbitrary JSON so you can see how DynamoDB stores it.
    model_config = ConfigDict(extra="allow")

    author: str
    message: str


def to_dynamo(value):
    """Convert Python values into what DynamoDB accepts.

    DynamoDB has one numeric type and boto3 refuses Python floats outright,
    because binary floats can't round-trip decimal values exactly. Decimal is
    the required substitute. Lists and dicts are walked so nested JSON works.
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    return value


@app.get("/")
def health():
    return {"status": "ok", "service": "feedback-api", "deployed_via": "github-oidc"}


@app.post("/feedback")
def create_feedback(item: FeedbackIn):
    # Spread the client's fields first so that "id" and "created_at" below
    # always win — otherwise a caller could supply an id and overwrite an
    # existing record, since put_item replaces any item with the same key.
    record = {
        **to_dynamo(item.model_dump()),
        "id": str(uuid.uuid4()),
        "created_at": int(time.time()),
    }
    try:
        get_table().put_item(Item=record)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail=f"DynamoDB unavailable: {exc}")
    return record


@app.get("/feedback")
def list_feedback():
    try:
        response = get_table().scan()
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail=f"DynamoDB unavailable: {exc}")
    items = response.get("Items", [])
    # Sort newest first
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return {"count": len(items), "items": items}


# Mangum wraps the FastAPI app so it can run inside AWS Lambda.
# This single line is what makes a normal web app "serverless".
handler = Mangum(app)
