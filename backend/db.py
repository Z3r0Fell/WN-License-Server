"""Shared MongoDB client and helpers."""
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_doc(doc):
    """Recursively serialize MongoDB doc: drop _id, convert datetime to ISO."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if k == "_id":
                continue
            out[k] = serialize_doc(v)
        return out
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
