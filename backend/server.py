"""WatchNexus Licensing Server - FastAPI entrypoint."""
import hashlib
import logging
import os
import secrets
import sys
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

sys.path.insert(0, str(ROOT_DIR))

from auth import hash_password, _client_ip
from crypto_core import _load_rsa_keys
from db import db, now_iso
from routers import admin as admin_router
from routers import admin_users as admin_users_router
from routers import customer as customer_router
from routers import integrate as integrate_router
from routers import orders as orders_router
from routers import public as public_router
from routers import quickstart as quickstart_router
from routers import subscriptions as subscriptions_router
from routers import updates as updates_router
from routers import webhooks_router
import runtime_settings

logging.basicConfig(level=logging.INFO,
                     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watchnexus")

RATE_RULES: list[tuple[str, int, int]] = [
    ("/api/admin/login",            10, 60),
    ("/api/customer/login",         15, 60),
    ("/api/customer/register",      5,  60),
    ("/api/integrate/activate",     60, 60),
    ("/api/integrate/validate",     600, 60),
    ("/api/integrate/deactivate",   30, 60),
    ("/api/integrate/mint",         30, 60),
    ("/api/webhooks",               300, 60),
    ("/api/orders",                 20, 60),
]

_buckets: dict[tuple[str, str], Deque[float]] = defaultdict(deque)


def _matched_rule(path: str) -> tuple[int, int] | None:
    for prefix, n, win in RATE_RULES:
        if path.startswith(prefix):
            return n, win
    return None


async def _ensure_ttl_index(collection, key: str, ttl_seconds: int) -> None:
    """Create a TTL index on a collection, converting any existing non-TTL
    index on the same key first (MongoDB errors on option conflicts)."""
    info = await collection.index_information()
    for name, spec in info.items():
        if tuple(spec.get("key", [])) == ((key, 1),):
            if spec.get("expireAfterSeconds") == ttl_seconds:
                return
            await collection.drop_index(name)
            break
    await collection.create_index(key, expireAfterSeconds=ttl_seconds)


app = FastAPI(title="WatchNexus Licensing Server", version="1.2.0")

# ---- Security headers middleware ----
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response

# ---- Request ID middleware ----
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# ---- Rate limit middleware ----
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    rule = _matched_rule(request.url.path)
    if rule:
        max_req, window = rule
        ip = _client_ip(request)
        key = (request.url.path, ip)
        now = time.monotonic()
        bucket = _buckets[key]
        cutoff = now - window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_req:
            retry_after = max(1, int(window - (now - bucket[0])))
            return JSONResponse(
                {"error": "rate_limit_exceeded",
                 "detail": f"Too many requests. Try again in {retry_after}s.",
                 "limit": max_req, "window_seconds": window},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
    return await call_next(request)


# Mount API routers under /api
from fastapi import APIRouter
api = APIRouter(prefix="/api")
api.include_router(public_router.router)
api.include_router(admin_router.router)
api.include_router(admin_users_router.router)
api.include_router(admin_users_router.public_router)
api.include_router(quickstart_router.router)
api.include_router(customer_router.router)
api.include_router(integrate_router.router)
api.include_router(orders_router.router)
api.include_router(subscriptions_router.router)
api.include_router(updates_router.router)
api.include_router(webhooks_router.router)
app.include_router(api)


def _get_cors_origins() -> list[str]:
    origins = os.environ.get("CORS_ORIGINS", "")
    if not origins:
        return []
    return [o.strip() for o in origins.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    _load_rsa_keys()
    await runtime_settings.refresh_cache()

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret or len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be set and at least 32 characters long")

    seed_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@watchnexus.app").lower()
    seed_pw = os.environ.get("SEED_ADMIN_PASSWORD")
    if not seed_pw or len(seed_pw) < 8:
        raise RuntimeError("SEED_ADMIN_PASSWORD must be set and at least 8 characters long")

    # Backfill key_hash for legacy API keys (created before hash-based lookup).
    # Must run before the unique key_hash index is built (null hashes would collide).
    legacy_keys = await db.api_keys.find({"key": {"$exists": True, "$ne": None},
                                          "key_hash": {"$exists": False}}).to_list(500)
    for rec in legacy_keys:
        raw_key = rec.get("key")
        if raw_key:
            await db.api_keys.update_one(
                {"id": rec["id"]},
                {"$set": {"key_hash": hashlib.sha256(raw_key.encode()).hexdigest()}})
    if legacy_keys:
        logger.info("Backfilled key_hash for %d legacy API key(s)", len(legacy_keys))

    # Indexes (idempotent; built before seed upserts so unique constraints hold)
    await db.licenses.create_index("key", unique=True)
    await db.licenses.create_index("customer_email")
    await db.licenses.create_index("product_id")
    await db.activations.create_index("license_id")
    await db.activations.create_index([("license_id", 1), ("fingerprint", 1)])
    await db.api_keys.create_index("key", unique=True)
    await db.api_keys.create_index("key_hash", unique=True)
    await db.audit_log.create_index("actor_id")
    await db.audit_log.create_index("actor_email")
    await db.webhook_events.create_index([("provider", 1), ("provider_event_id", 1)])
    await db.customers.create_index("email", unique=True)
    await db.admin_users.create_index("email", unique=True)
    await db.admin_invites.create_index("token", unique=True)
    await db.admin_invites.create_index("email")
    await db.orders.create_index("reference", unique=True)
    await db.orders.create_index("status")
    await db.orders.create_index("created_at")
    await db.lockouts.create_index("key", unique=True)
    await db.lockouts.create_index("until")
    await _ensure_ttl_index(db.audit_log, "ts", 2592000)
    await _ensure_ttl_index(db.webhook_events, "received_at", 2592000)

    # Seeds (race-safe upserts; uvicorn runs on_startup per worker)
    from pymongo.errors import DuplicateKeyError

    async def _seed(collection, filt: dict, doc: dict) -> None:
        try:
            await collection.update_one(filt, {"$setOnInsert": doc}, upsert=True)
        except DuplicateKeyError:
            pass  # another worker seeded it first

    await _seed(db.admin_users, {"email": seed_email}, {
        "id": str(uuid.uuid4()),
        "email": seed_email,
        "name": "Admin",
        "password_hash": hash_password(seed_pw),
        "admin_role": "admin",
        "is_active": True,
        "created_at": now_iso(),
        "last_login_at": None,
    })
    await db.admin_users.update_many(
        {"admin_role": {"$exists": False}},
        {"$set": {"admin_role": "admin"}},
    )
    await db.admin_users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}},
    )
    await _seed(db.products, {"slug": "watchnexus-pro"}, {
        "id": str(uuid.uuid4()),
        "name": "WatchNexus Pro",
        "slug": "watchnexus-pro",
        "signing_method": "hmac",
        "fingerprint_mode": "both",
        "max_seats_default": 3,
        "description": "Default product for WatchNexus.",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    boot_raw = "wnk_" + secrets.token_urlsafe(32)
    await _seed(db.api_keys, {"is_bootstrap": True, "status": "active"}, {
        "id": str(uuid.uuid4()),
        "name": "WatchNexus App Suite (bootstrap)",
        "product_id": None,
        "scopes": ["activate", "validate", "deactivate"],
        "allowed_ips": [],
        "key": boot_raw,
        "key_hash": hashlib.sha256(boot_raw.encode()).hexdigest(),
        "is_bootstrap": True,
        "status": "active",
        "created_at": now_iso(),
        "last_used_at": None,
        "last_used_ip": None,
    })
    boot = await db.api_keys.find_one({"is_bootstrap": True, "status": "active"}, {"_id": 0})
    if boot and not boot.get("key_hash") and boot.get("key"):
        await db.api_keys.update_one(
            {"id": boot["id"]},
            {"$set": {"key_hash": hashlib.sha256(boot["key"].encode()).hexdigest()}})

    if await db.products.count_documents({}) > 0:
        product = await db.products.find_one({"slug": "watchnexus-pro"}, {"_id": 0}) \
            or await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
        has_demo = await db.licenses.find_one(
            {"is_bootstrap": True, "status": "active", "product_id": product["id"]}, {"_id": 0})
        if not has_demo:
            from crypto_core import generate_license_key
            try:
                await db.licenses.insert_one({
                    "id": str(uuid.uuid4()),
                    "key": generate_license_key("demo"),
                    "product_id": product["id"],
                    "product_slug": product["slug"],
                    "signing_method": "short",
                    "fingerprint_mode": product["fingerprint_mode"],
                    "customer_email": None,
                    "customer_id": None,
                    "plan": "demo",
                    "seats": 3,
                    "expires_at": None,
                    "notes": "Demo license auto-generated for the quickstart. Safe to revoke later.",
                    "status": "active",
                    "source": "bootstrap",
                    "is_bootstrap": True,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                })
            except DuplicateKeyError:
                pass
            logger.info("Seeded demo license under product '%s'", product["slug"])
    logger.info("WatchNexus Licensing Server ready")


@app.on_event("shutdown")
async def on_shutdown():
    from db import client
    client.close()


@app.get("/")
async def root():
    return {"service": "WatchNexus Licensing Server", "ok": True}
