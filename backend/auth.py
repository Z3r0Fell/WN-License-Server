"""Authentication helpers: password hashing, JWT issuance, dependencies."""
import os
import time
import uuid
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import db, serialize_doc

bearer = HTTPBearer(auto_error=False)

SESSION_TTL = 60 * 60 * 24 * 7  # 7d


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _secret() -> str:
    return os.environ.get("JWT_SECRET", "dev-secret")


def issue_session_token(subject_id: str, role: str, email: str) -> str:
    now = int(time.time())
    claims = {
        "sub": subject_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + SESSION_TTL,
        "iss": "watchnexus-session",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, _secret(), algorithm="HS256")


def _decode(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"], issuer="watchnexus-session")
    except jwt.InvalidTokenError:
        return None


async def get_current_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = _decode(creds.credentials)
    if not claims or claims.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Invalid admin token")
    user = await db.admin_users.find_one({"id": claims["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Admin not found")
    return serialize_doc(user)


async def get_current_customer(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = _decode(creds.credentials)
    if not claims or claims.get("role") != "customer":
        raise HTTPException(status_code=401, detail="Invalid customer token")
    user = await db.customers.find_one({"id": claims["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Customer not found")
    return serialize_doc(user)


async def get_api_key(request: Request) -> dict:
    """Server-to-server API key auth for /integrate/*. Header: X-API-Key."""
    raw = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if not raw:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    rec = await db.api_keys.find_one({"key": raw, "status": "active"}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # update last_used (fire and forget)
    from db import now_iso
    await db.api_keys.update_one({"id": rec["id"]}, {"$set": {"last_used_at": now_iso()}})
    return serialize_doc(rec)
