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
    # Block disabled accounts even if they still hold a valid JWT.
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    # Ensure legacy users without a role still get the admin role for compatibility.
    user.setdefault("admin_role", "admin")
    return serialize_doc(user)


def require_admin_role(*allowed_roles: str):
    """Dependency factory: gate an endpoint by admin_role.

    Usage:
        @router.post(..., dependencies=[Depends(require_admin_role("admin"))])

    Or to receive the user object:
        async def my_handler(admin=Depends(get_current_admin)):
            require_admin_role("admin")(admin)
    """
    allowed = set(allowed_roles)

    async def _dep(admin: dict = Depends(get_current_admin)) -> dict:
        role = admin.get("admin_role") or "admin"
        if role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"This action requires one of roles: {', '.join(sorted(allowed))}",
            )
        return admin

    return _dep


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
    """Server-to-server API key auth for /integrate/*. Header: X-API-Key.
    Enforces per-key IP allowlist (CIDR aware)."""
    raw = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if not raw:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    rec = await db.api_keys.find_one({"key": raw, "status": "active"}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # IP allowlist
    from webhooks_sig import ip_in_allowlist
    client_ip = _client_ip(request)
    allowlist = rec.get("allowed_ips") or []
    if allowlist and not ip_in_allowlist(client_ip, allowlist):
        raise HTTPException(status_code=403,
                            detail=f"IP {client_ip} not allowed for this API key")
    # update last_used (fire and forget)
    from db import now_iso
    await db.api_keys.update_one({"id": rec["id"]},
                                 {"$set": {"last_used_at": now_iso(),
                                           "last_used_ip": client_ip}})
    return serialize_doc(rec)


def _client_ip(request: Request) -> str | None:
    """Return the real client IP, honoring common proxy headers."""
    # X-Forwarded-For: client, proxy1, proxy2 -> take the first
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
    if real:
        return real.strip()
    return request.client.host if request.client else None
