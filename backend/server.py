"""WatchNexus Licensing Server - FastAPI entrypoint."""
import logging
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Ensure backend dir on path so 'routers' resolves
sys.path.insert(0, str(ROOT_DIR))

from auth import hash_password
from crypto_core import _load_rsa_keys
from db import db, now_iso
from routers import admin as admin_router
from routers import admin_users as admin_users_router
from routers import customer as customer_router
from routers import integrate as integrate_router
from routers import public as public_router
from routers import quickstart as quickstart_router
from routers import subscriptions as subscriptions_router
from routers import webhooks_router
import runtime_settings

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watchnexus")


# ---- Per-route rate limit buckets (sliding window in-memory) -----------------
# Each rule: prefix -> (max_requests, window_seconds)
RATE_RULES: list[tuple[str, int, int]] = [
    ("/api/admin/login",            10, 60),    # brute-force protection
    ("/api/customer/login",         15, 60),
    ("/api/customer/register",      5,  60),
    ("/api/integrate/activate",     60, 60),    # ~1/sec sustained
    ("/api/integrate/validate",     600, 60),   # heartbeats are common
    ("/api/integrate/deactivate",   30, 60),
    ("/api/integrate/mint",         30, 60),    # website purchase webhooks
    ("/api/webhooks",               300, 60),   # bursts from providers
]

_buckets: dict[tuple[str, str], Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def _matched_rule(path: str) -> tuple[int, int] | None:
    for prefix, n, win in RATE_RULES:
        if path.startswith(prefix):
            return n, win
    return None


app = FastAPI(title="WatchNexus Licensing Server", version="1.1.0")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    rule = _matched_rule(request.url.path)
    if rule:
        max_req, window = rule
        ip = _client_ip(request)
        key = (request.url.path, ip)
        now = time.monotonic()
        bucket = _buckets[key]
        # drop old
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
api.include_router(subscriptions_router.router)
api.include_router(webhooks_router.router)
app.include_router(api)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    _load_rsa_keys()
    await runtime_settings.refresh_cache()
    seed_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@watchnexus.app").lower()
    seed_pw = os.environ.get("SEED_ADMIN_PASSWORD", "admin12345")
    existing = await db.admin_users.find_one({"email": seed_email})
    if not existing:
        import uuid
        await db.admin_users.insert_one({
            "id": str(uuid.uuid4()),
            "email": seed_email,
            "name": "Admin",
            "password_hash": hash_password(seed_pw),
            "admin_role": "admin",
            "is_active": True,
            "created_at": now_iso(),
            "last_login_at": None,
        })
        logger.info(f"Seeded admin user: {seed_email}")

    # Backfill role/is_active on any pre-existing admin docs that predate this field.
    await db.admin_users.update_many(
        {"admin_role": {"$exists": False}},
        {"$set": {"admin_role": "admin"}},
    )
    await db.admin_users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}},
    )
    if await db.products.count_documents({}) == 0:
        import uuid
        pid = str(uuid.uuid4())
        await db.products.insert_one({
            "id": pid,
            "name": "WatchNexus Pro",
            "slug": "watchnexus-pro",
            "signing_method": "hmac",
            "fingerprint_mode": "both",
            "max_seats_default": 3,
            "description": "Default product for WatchNexus.",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        logger.info("Seeded default product 'watchnexus-pro'")

    # -------- Bootstrap integration kit --------
    # A persistent API key + a demo license, so the WatchNexus app suite has
    # something to talk to without any admin clicks. Rotate via admin UI later.
    import secrets
    import uuid
    from crypto_core import generate_license_key
    existing_boot = await db.api_keys.find_one({"is_bootstrap": True, "status": "active"})
    if not existing_boot:
        product = await db.products.find_one({"slug": "watchnexus-pro"}, {"_id": 0}) \
            or await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
        raw = "wnk_" + secrets.token_urlsafe(32)
        await db.api_keys.insert_one({
            "id": str(uuid.uuid4()),
            "name": "WatchNexus App Suite (bootstrap)",
            "product_id": None,
            "scopes": ["activate", "validate", "deactivate"],
            "allowed_ips": [],
            "key": raw,
            "is_bootstrap": True,
            "status": "active",
            "created_at": now_iso(),
            "last_used_at": None,
            "last_used_ip": None,
        })
        logger.warning("=" * 60)
        logger.warning("WATCHNEXUS BOOTSTRAP API KEY (use to integrate your app):")
        logger.warning("  %s", raw)
        logger.warning("Find this any time at /admin/quickstart in the admin panel.")
        logger.warning("=" * 60)

        # Demo license under the default product, no email, 3 seats
        if product:
            demo_id = str(uuid.uuid4())
            demo_key = generate_license_key("demo")
            await db.licenses.insert_one({
                "id": demo_id,
                "key": demo_key,
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
            logger.info("Seeded demo license under product '%s'", product["slug"])
    await db.licenses.create_index("key", unique=True)
    await db.licenses.create_index("customer_email")
    await db.licenses.create_index("product_id")
    await db.activations.create_index("license_id")
    await db.activations.create_index([("license_id", 1), ("fingerprint", 1)])
    await db.api_keys.create_index("key", unique=True)
    await db.audit_log.create_index("ts")
    await db.audit_log.create_index("actor_id")
    await db.audit_log.create_index("actor_email")
    await db.webhook_events.create_index("received_at")
    await db.webhook_events.create_index([("provider", 1), ("provider_event_id", 1)])
    await db.customers.create_index("email", unique=True)
    await db.admin_users.create_index("email", unique=True)
    await db.admin_invites.create_index("token", unique=True)
    await db.admin_invites.create_index("email")
    logger.info("WatchNexus Licensing Server ready")


@app.on_event("shutdown")
async def on_shutdown():
    from db import client
    client.close()


@app.get("/")
async def root():
    return {"service": "WatchNexus Licensing Server", "ok": True}
