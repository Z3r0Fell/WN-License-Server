"""Webhook receiver routes for Lemon Squeezy / Paddle / Gumroad."""
import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from audit import log as audit_log
from db import db, now_iso, serialize_doc
from webhooks_sig import (extract_email_gumroad, extract_email_lemonsqueezy,
                          extract_email_paddle, verify_gumroad,
                          verify_lemonsqueezy, verify_paddle)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _store_event(provider: str, event_type: str, status: str,
                       raw_body: bytes, parsed: Any, error: str | None = None,
                       provider_event_id: str | None = None,
                       license_id: str | None = None) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "provider": provider,
        "event_type": event_type,
        "status": status,
        "received_at": now_iso(),
        "raw": raw_body.decode("utf-8", errors="replace"),
        "parsed": parsed if isinstance(parsed, dict) else None,
        "error": error,
        "provider_event_id": provider_event_id,
        "license_id": license_id,
    }
    await db.webhook_events.insert_one(doc)
    return doc


async def _is_duplicate(provider: str, provider_event_id: str | None) -> bool:
    if not provider_event_id:
        return False
    existing = await db.webhook_events.find_one(
        {"provider": provider, "provider_event_id": provider_event_id, "status": "processed"})
    return existing is not None


async def _provision_license(email: str | None, product_slug_hint: str | None,
                              plan: str = "standard") -> str | None:
    """Create license tied to email + a product.  Picks first matching product slug,
    falling back to the first product if no hint."""
    if not email:
        return None
    product = None
    if product_slug_hint:
        product = await db.products.find_one({"slug": product_slug_hint}, {"_id": 0})
    if not product:
        product = await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    if not product:
        return None
    # Use admin._create_license logic inline (avoid circular import)
    from crypto_core import generate_hmac_license, generate_rsa_license
    license_id = str(uuid.uuid4())
    if product["signing_method"] == "rsa":
        key = generate_rsa_license(license_id, product["slug"])
    else:
        secret = os.environ.get("HMAC_LICENSE_SECRET", "dev").encode()
        key = generate_hmac_license(license_id, product["slug"], secret)
    customer = await db.customers.find_one({"email": email.lower()}, {"_id": 0})
    doc = {
        "id": license_id,
        "key": key,
        "product_id": product["id"],
        "product_slug": product["slug"],
        "signing_method": product["signing_method"],
        "fingerprint_mode": product["fingerprint_mode"],
        "customer_email": email.lower(),
        "customer_id": customer["id"] if customer else None,
        "plan": plan,
        "seats": product.get("max_seats_default", 1),
        "expires_at": None,
        "notes": None,
        "status": "active",
        "source": "webhook",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(doc)
    await audit_log("webhook", None, None, "license.create", "license", license_id,
                    meta={"product": product["slug"], "email": email})
    return license_id


# ---------------- Lemon Squeezy ----------------
@router.post("/lemonsqueezy")
async def lemonsqueezy(request: Request):
    body = await request.body()
    sig = request.headers.get("x-signature", "")
    secret = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
    if not verify_lemonsqueezy(body, sig, secret):
        await _store_event("lemonsqueezy", "unknown", "signature_invalid", body, None,
                           error="signature mismatch")
        raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(body)
    except Exception as e:
        await _store_event("lemonsqueezy", "unknown", "parse_error", body, None, error=str(e))
        raise HTTPException(400, "Invalid JSON")
    event_type = payload.get("meta", {}).get("event_name", "unknown")
    provider_event_id = payload.get("meta", {}).get("event_id") or payload.get("data", {}).get("id")
    if await _is_duplicate("lemonsqueezy", provider_event_id):
        await _store_event("lemonsqueezy", event_type, "duplicate", body, payload,
                           provider_event_id=provider_event_id)
        return {"ok": True, "duplicate": True}
    license_id = None
    if event_type in ("order_created", "subscription_created", "subscription_payment_success"):
        email = extract_email_lemonsqueezy(payload)
        product_slug = payload.get("meta", {}).get("custom_data", {}).get("product_slug")
        license_id = await _provision_license(email, product_slug, plan="lemonsqueezy")
    await _store_event("lemonsqueezy", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id}


# ---------------- Paddle ----------------
@router.post("/paddle")
async def paddle(request: Request):
    body = await request.body()
    sig = request.headers.get("paddle-signature", "")
    secret = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
    if not verify_paddle(body, sig, secret):
        await _store_event("paddle", "unknown", "signature_invalid", body, None,
                           error="signature mismatch or expired")
        raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(body)
    except Exception as e:
        await _store_event("paddle", "unknown", "parse_error", body, None, error=str(e))
        raise HTTPException(400, "Invalid JSON")
    event_type = payload.get("event_type", "unknown")
    provider_event_id = payload.get("event_id") or payload.get("notification_id")
    if await _is_duplicate("paddle", provider_event_id):
        await _store_event("paddle", event_type, "duplicate", body, payload,
                           provider_event_id=provider_event_id)
        return {"ok": True, "duplicate": True}
    license_id = None
    if event_type in ("transaction.completed", "subscription.created", "subscription.activated"):
        email = extract_email_paddle(payload)
        product_slug = payload.get("data", {}).get("custom_data", {}).get("product_slug") if isinstance(payload.get("data"), dict) else None
        license_id = await _provision_license(email, product_slug, plan="paddle")
    await _store_event("paddle", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id}


# ---------------- Gumroad ----------------
@router.post("/gumroad")
async def gumroad(request: Request):
    body = await request.body()
    sig = request.headers.get("x-gumroad-signature", "")
    secret = os.environ.get("GUMROAD_WEBHOOK_SECRET", "")
    if not verify_gumroad(body, sig, secret):
        await _store_event("gumroad", "unknown", "signature_invalid", body, None,
                           error="signature mismatch")
        raise HTTPException(401, "Invalid signature")
    # Gumroad legacy pings can be form-encoded; modern resource subscription is JSON.
    try:
        payload = json.loads(body)
    except Exception:
        from urllib.parse import parse_qs
        try:
            qs = parse_qs(body.decode("utf-8", errors="replace"))
            payload = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in qs.items()}
        except Exception as e:
            await _store_event("gumroad", "unknown", "parse_error", body, None, error=str(e))
            raise HTTPException(400, "Invalid body")
    event_type = payload.get("resource_name") or payload.get("event") or "sale"
    provider_event_id = payload.get("sale_id") or payload.get("id")
    if await _is_duplicate("gumroad", provider_event_id):
        await _store_event("gumroad", event_type, "duplicate", body, payload,
                           provider_event_id=provider_event_id)
        return {"ok": True, "duplicate": True}
    license_id = None
    email = extract_email_gumroad(payload)
    product_slug = payload.get("product_permalink") or payload.get("product_id")
    license_id = await _provision_license(email, product_slug, plan="gumroad")
    await _store_event("gumroad", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id}
