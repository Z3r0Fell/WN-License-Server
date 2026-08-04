"""Quickstart / Integration Kit endpoints.

Surfaces a ready-to-use API key + demo license + public base URL so the
WatchNexus application suite can be tied in without manual setup.

The demo license is **per product** - so when an admin clicks `Quickstart`
they can pick which product to test against, and a dedicated bootstrap
demo license is lazily created under that product the first time.
"""
import os
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_admin
from audit import log as audit_log
from crypto_core import (compute_fingerprint, issue_activation_token,
                         validate_activation_token)
from db import db, now_iso, serialize_doc

router = APIRouter(prefix="/admin/quickstart", tags=["quickstart"])


def _public_base_url(request: Request) -> str:
    """Return the public-facing base URL the client should use."""
    env = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
    if env:
        return env
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


async def _bootstrap_key_record() -> dict | None:
    return await db.api_keys.find_one({"is_bootstrap": True, "status": "active"}, {"_id": 0})


async def _bootstrap_license_for_product(product_id: str) -> dict | None:
    return await db.licenses.find_one(
        {"is_bootstrap": True, "status": "active", "product_id": product_id},
        {"_id": 0},
    )


async def _ensure_bootstrap_key() -> dict:
    """Make sure a bootstrap API key exists. Creates lazily if missing."""
    key_rec = await _bootstrap_key_record()
    if key_rec:
        return key_rec
    raw = "wnk_" + secrets.token_urlsafe(32)
    doc = {
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
    }
    await db.api_keys.insert_one(doc)
    return doc


async def _ensure_bootstrap_license(product: dict) -> dict:
    """Ensure a per-product bootstrap demo license exists. Creates lazily."""
    from crypto_core import generate_license_key

    existing = await _bootstrap_license_for_product(product["id"])
    if existing:
        return existing

    license_id = str(uuid.uuid4())
    lic_key = generate_license_key("demo")
    doc = {
        "id": license_id,
        "key": lic_key,
        "product_id": product["id"],
        "product_slug": product["slug"],
        "signing_method": "short",
        "fingerprint_mode": product["fingerprint_mode"],
        "customer_email": None,
        "customer_id": None,
        "plan": "demo",
        "seats": max(3, product.get("max_seats_default", 1)),
        "expires_at": None,
        "notes": f"Demo license for product '{product['slug']}', auto-generated for the Quickstart.",
        "status": "active",
        "source": "bootstrap",
        "is_bootstrap": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(doc)
    return doc


async def _resolve_product(product_id: Optional[str]) -> dict | None:
    if product_id:
        p = await db.products.find_one({"id": product_id}, {"_id": 0})
        if p:
            return p
    # Fallback to first product (oldest) - the typical "watchnexus-pro"
    return await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])


@router.get("")
async def quickstart_info(request: Request,
                          product_id: Optional[str] = None,
                          admin=Depends(get_current_admin)):
    key_rec = await _ensure_bootstrap_key()
    product = await _resolve_product(product_id)
    lic_rec = await _ensure_bootstrap_license(product) if product else None

    products = await db.products.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)
    base = _public_base_url(request)

    return {
        "base_url": base,
        "api_key": key_rec["key"],
        "api_key_id": key_rec["id"],
        "api_key_name": key_rec["name"],
        "api_key_allowed_ips": key_rec.get("allowed_ips", []),
        "selected_product_id": product["id"] if product else None,
        "products": [
            {
                "id": p["id"], "name": p["name"], "slug": p["slug"],
                "signing_method": p["signing_method"],
                "fingerprint_mode": p["fingerprint_mode"],
                "max_seats_default": p.get("max_seats_default", 1),
            } for p in products
        ],
        "demo_license": serialize_doc(lic_rec) if lic_rec else None,
        "endpoints": {
            "activate":   f"{base}/api/integrate/activate",
            "validate":   f"{base}/api/integrate/validate",
            "deactivate": f"{base}/api/integrate/deactivate",
            "public_key": f"{base}/api/public-key",
            "health":     f"{base}/api/health",
        },
        "fingerprint_sample": {
            "hardware_id": "01:23:45:67:89:AB",
            "domain": "customer.example.com",
            "device_name": "Marketing Laptop",
        },
    }


@router.post("/rotate-key")
async def rotate_key(admin=Depends(get_current_admin)):
    """Revoke the existing bootstrap key and mint a new one."""
    await db.api_keys.update_many({"is_bootstrap": True, "status": "active"},
                                  {"$set": {"status": "revoked"}})
    raw = "wnk_" + secrets.token_urlsafe(32)
    doc = {
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
    }
    await db.api_keys.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "api_key.bootstrap_rotate",
                    "api_key", doc["id"], severity="warning")
    return {"api_key": raw, "id": doc["id"], "created_at": doc["created_at"]}


class TestRunIn(BaseModel):
    product_id: Optional[str] = None
    license_key: Optional[str] = None
    hardware_id: Optional[str] = "01:23:45:67:89:AB"
    domain: Optional[str] = "quickstart.example.com"
    device_name: Optional[str] = "Quickstart Test Device"


@router.post("/test")
async def test_run(body: TestRunIn, request: Request, admin=Depends(get_current_admin)):
    """Run a real activate -> validate -> deactivate cycle using the
    bootstrap key against the selected product's demo license."""
    await _ensure_bootstrap_key()

    if body.license_key:
        lic = await db.licenses.find_one({"key": body.license_key}, {"_id": 0})
    else:
        product = await _resolve_product(body.product_id)
        if not product:
            raise HTTPException(400, "No product available to test against. Create one first.")
        lic = await _ensure_bootstrap_license(product)

    if not lic:
        raise HTTPException(400, "License not found")

    steps = []
    hw = (body.hardware_id or "01:23:45:67:89:AB") + ":" + secrets.token_hex(2)
    fp = compute_fingerprint(lic["fingerprint_mode"], hw, body.domain)

    # Seat recycle for repeated tests
    active_count = await db.activations.count_documents(
        {"license_id": lic["id"], "status": "active"})
    if active_count >= lic["seats"]:
        oldest = await db.activations.find_one(
            {"license_id": lic["id"], "status": "active",
             "source": "quickstart_test"},
            sort=[("created_at", 1)],
        )
        if oldest:
            await db.activations.update_one(
                {"id": oldest["id"]},
                {"$set": {"status": "deactivated",
                          "deactivated_at": now_iso(),
                          "deactivated_reason": "quickstart_seat_recycle"}})

    # 1. Activate
    aid = str(uuid.uuid4())
    activation = {
        "id": aid,
        "license_id": lic["id"],
        "product_slug": lic["product_slug"],
        "customer_email": lic.get("customer_email"),
        "fingerprint": fp,
        "hardware_id": hw,
        "domain": body.domain,
        "device_name": body.device_name,
        "status": "active",
        "created_at": now_iso(),
        "last_seen_at": now_iso(),
        "first_ip": request.client.host if request.client else None,
        "last_ip": request.client.host if request.client else None,
        "source": "quickstart_test",
    }
    await db.activations.insert_one(activation)
    token = issue_activation_token(lic["id"], fp, aid)
    steps.append({
        "label": "POST /api/integrate/activate",
        "status": 200,
        "response": {
            "activation_id": aid,
            "activation_token": token["token"],
            "expires_at": token["exp"],
            "grace_until": token["grace_until"],
            "license": {"id": lic["id"], "plan": lic["plan"], "product": lic["product_slug"]},
            "reused": False,
        },
    })

    # 2. Validate
    decoded = validate_activation_token(token["token"], expected_fp=fp)
    steps.append({
        "label": "POST /api/integrate/validate",
        "status": 200,
        "response": {
            "valid": decoded["valid"],
            "mode": decoded.get("mode"),
            "license": {"id": lic["id"], "plan": lic["plan"], "product": lic["product_slug"],
                        "expires_at": lic.get("expires_at"), "seats": lic["seats"]},
            "activation": {"id": aid, "device_name": body.device_name},
            "expires_at": token["exp"],
            "grace_until": token["grace_until"],
        },
    })

    # 3. Deactivate
    await db.activations.update_one(
        {"id": aid, "status": "active"},
        {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                  "deactivated_reason": "quickstart_test"}})
    steps.append({
        "label": "POST /api/integrate/deactivate",
        "status": 200,
        "response": {"ok": True, "activation_id": aid},
    })

    await audit_log("admin", admin["id"], admin["email"], "quickstart.test_run",
                    "license", lic["id"], severity="info",
                    meta={"product": lic["product_slug"], "steps": 3,
                          "fingerprint": fp[:16]},
                    ip=request.client.host if request.client else None)

    return {
        "ok": True,
        "license_key": lic["key"],
        "product_slug": lic["product_slug"],
        "fingerprint": fp,
        "steps": steps,
    }
