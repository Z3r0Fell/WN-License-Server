"""WatchNexus Licensing Server - FastAPI entrypoint."""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
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
from routers import customer as customer_router
from routers import integrate as integrate_router
from routers import public as public_router
from routers import webhooks_router

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watchnexus")

# ----- Rate limiting -----
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/minute"],
    storage_uri="memory://",
    strategy="moving-window",
)

app = FastAPI(title="WatchNexus Licensing Server", version="1.0.0")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        {"error": "rate_limit_exceeded", "detail": str(exc.detail)},
        status_code=429,
    )


# Apply tighter rate limits to specific endpoints by path-prefix middleware
@app.middleware("http")
async def per_path_rate_limits(request: Request, call_next):
    # The library applies default_limits globally; tighter per-route via decorator OR
    # we can short-circuit here using its limit() helper. Keeping default global limit.
    return await call_next(request)


# Mount API routers under /api
from fastapi import APIRouter
api = APIRouter(prefix="/api")
api.include_router(public_router.router)
api.include_router(admin_router.router)
api.include_router(customer_router.router)
api.include_router(integrate_router.router)
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
    # Pre-load RSA keys (creates them if missing)
    _load_rsa_keys()
    # Seed admin user
    seed_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@watchnexus.local").lower()
    seed_pw = os.environ.get("SEED_ADMIN_PASSWORD", "admin12345")
    existing = await db.admin_users.find_one({"email": seed_email})
    if not existing:
        import uuid
        await db.admin_users.insert_one({
            "id": str(uuid.uuid4()),
            "email": seed_email,
            "name": "Admin",
            "password_hash": hash_password(seed_pw),
            "created_at": now_iso(),
        })
        logger.info(f"Seeded admin user: {seed_email}")
    # Seed example product if none exist
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
    # Useful indexes
    await db.licenses.create_index("key", unique=True)
    await db.licenses.create_index("customer_email")
    await db.licenses.create_index("product_id")
    await db.activations.create_index("license_id")
    await db.activations.create_index([("license_id", 1), ("fingerprint", 1)])
    await db.api_keys.create_index("key", unique=True)
    await db.audit_log.create_index("ts")
    await db.webhook_events.create_index("received_at")
    await db.webhook_events.create_index([("provider", 1), ("provider_event_id", 1)])
    await db.customers.create_index("email", unique=True)
    await db.admin_users.create_index("email", unique=True)
    logger.info("WatchNexus Licensing Server ready")


@app.on_event("shutdown")
async def on_shutdown():
    from db import client
    client.close()


@app.get("/")
async def root():
    return {"service": "WatchNexus Licensing Server", "ok": True}
