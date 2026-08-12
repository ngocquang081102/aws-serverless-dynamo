import os
import time
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mangum import Mangum

app = FastAPI(title="Feedback API")

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
    author: str
    message: str


@app.get("/")
def health():
    return {"status": "ok", "service": "feedback-api"}


@app.post("/feedback")
def create_feedback(item: FeedbackIn):
    record = {
        "id": str(uuid.uuid4()),
        "author": item.author,
        "message": item.message,
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
