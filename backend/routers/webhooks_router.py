"""Webhook receiver routes for Lemon Squeezy / Paddle / Gumroad / Stripe."""
import json
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from audit import log as audit_log
from db import db, now_iso
from email_sender import render_purchase_email, send_email
from webhooks_sig import (
    extract_email_gumroad, extract_email_lemonsqueezy, extract_email_paddle,
    extract_email_stripe, verify_gumroad, verify_lemonsqueezy, verify_paddle,
    verify_stripe,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("watchnexus.webhooks")


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
                              plan: str = "standard", source: str = "webhook") -> str | None:
    """Create license tied to email + a product, then email the customer."""
    if not email:
        return None
    product = None
    if product_slug_hint:
        product = await db.products.find_one({"slug": product_slug_hint}, {"_id": 0})
    if not product:
        product = await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    if not product:
        return None
    from crypto_core import generate_hmac_license, generate_rsa_license
    license_id = str(uuid.uuid4())
    if product["signing_method"] == "rsa":
        key = generate_rsa_license(license_id, product["slug"])
    else:
        secret = os.environ.get("HMAC_LICENSE_SECRET", "dev").encode()
        key = generate_hmac_license(license_id, product["slug"], secret)
    customer = await db.customers.find_one({"email": email.lower()}, {"_id": 0})
    seats = product.get("max_seats_default", 1)
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
        "seats": seats,
        "expires_at": None,
        "notes": None,
        "status": "active",
        "source": source,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(doc)
    await audit_log("webhook", None, None, "license.create", "license", license_id,
                    meta={"product": product["slug"], "email": email, "source": source})

    # Fire-and-forget email
    try:
        portal_url = os.environ.get("APP_PUBLIC_URL", "").rstrip("/") + "/portal"
        subject, html = render_purchase_email(
            customer_email=email,
            license_key=key,
            product_name=product.get("name") or product["slug"],
            plan=plan,
            seats=seats,
            source=source,
            portal_url=portal_url,
        )
        result = send_email(email, subject, html)
        await audit_log("system", None, None, "email.purchase_confirmation",
                        "license", license_id,
                        severity="info" if result.get("sent") else "warning",
                        meta={"to": email, "provider": result.get("provider"),
                              "sent": result.get("sent", False)})
    except Exception as e:
        logger.exception("purchase email render/send failed")
        await audit_log("system", None, None, "email.purchase_confirmation",
                        "license", license_id, severity="error", meta={"error": str(e)})

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
        license_id = await _provision_license(email, product_slug, plan="lemonsqueezy",
                                              source="lemonsqueezy")
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
        d = payload.get("data") or {}
        product_slug = (d.get("custom_data") or {}).get("product_slug") if isinstance(d, dict) else None
        license_id = await _provision_license(email, product_slug, plan="paddle", source="paddle")
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
    email = extract_email_gumroad(payload)
    product_slug = payload.get("product_permalink") or payload.get("product_id")
    license_id = await _provision_license(email, product_slug, plan="gumroad", source="gumroad")
    await _store_event("gumroad", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id}


# ---------------- Stripe ----------------
@router.post("/stripe")
async def stripe(request: Request):
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not verify_stripe(body, sig, secret):
        await _store_event("stripe", "unknown", "signature_invalid", body, None,
                           error="signature mismatch or expired")
        raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(body)
    except Exception as e:
        await _store_event("stripe", "unknown", "parse_error", body, None, error=str(e))
        raise HTTPException(400, "Invalid JSON")
    event_type = payload.get("type", "unknown")
    provider_event_id = payload.get("id")
    if await _is_duplicate("stripe", provider_event_id):
        await _store_event("stripe", event_type, "duplicate", body, payload,
                           provider_event_id=provider_event_id)
        return {"ok": True, "duplicate": True}
    license_id = None
    # Issue a license on completed checkout / paid invoice / payment success.
    if event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "invoice.paid",
        "invoice.payment_succeeded",
        "payment_intent.succeeded",
        "customer.subscription.created",
    ):
        email = extract_email_stripe(payload)
        obj = payload.get("data", {}).get("object", {}) or {}
        meta = obj.get("metadata") or {}
        product_slug = meta.get("product_slug")
        license_id = await _provision_license(email, product_slug, plan="stripe", source="stripe")
    await _store_event("stripe", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id}
