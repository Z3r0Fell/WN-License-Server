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
import runtime_settings
from routers.subscriptions import _subscription_sync_licenses
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


async def _provision_subscription(email: str | None, product_slug_hint: str | None,
                                   plan: str = "standard", source: str = "webhook",
                                   provider_sub_id: str | None = None,
                                   billing_period: str = "monthly",
                                   price: float = 0,
                                   currency: str = "USD") -> str | None:
    """Create or update a subscription from a webhook event."""
    if not email:
        return None
    product = None
    if product_slug_hint:
        product = await db.products.find_one({"slug": product_slug_hint}, {"_id": 0})
    if not product:
        product = await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    if not product:
        return None

    # Find matching subscription plan by slug or create a dynamic one
    plan_slug = f"{source}-{plan}"
    sub_plan = await db.subscription_plans.find_one({"slug": plan_slug}, {"_id": 0})
    if not sub_plan:
        pid = str(uuid.uuid4())
        sub_plan = {
            "id": pid,
            "name": f"{product.get('name', product['slug'])} ({source})",
            "slug": plan_slug,
            "description": f"Auto-created from {source} webhook",
            "product_id": product["id"],
            "product_slug": product["slug"],
            "billing_options": [{"period": billing_period, "price": price, "currency": currency}],
            "features": [],
            "max_seats": product.get("max_seats_default", 1),
            "max_activations": None,
            "grace_days": 7,
            "trial_days": None,
            "status": "active",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await db.subscription_plans.insert_one(sub_plan)

    customer = await db.customers.find_one({"email": email.lower()}, {"_id": 0})

    # Check for existing subscription by provider sub id
    existing = None
    if provider_sub_id:
        existing = await db.subscriptions.find_one(
            {"payment_provider_subscription_id": provider_sub_id}, {"_id": 0})

    if existing:
        # Renew: extend period, keep active
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        period_map = {"monthly": 30, "yearly": 365, "quarterly": 90}
        days = period_map.get(billing_period, 30)
        update = {
            "status": "active",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=days)).isoformat(),
            "price": price,
            "currency": currency,
            "billing_period": billing_period,
            "auto_renew": True,
            "updated_at": now_iso(),
        }
        await db.subscriptions.update_one({"id": existing["id"]}, {"$set": update})
        await _subscription_sync_licenses({**existing, **update})
        await audit_log("webhook", None, None, "subscription.renewed",
                        "subscription", existing["id"],
                        meta={"source": source, "provider_sub_id": provider_sub_id})
        return existing["id"]

    # Create new subscription
    sid = str(uuid.uuid4())
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    period_map = {"monthly": 30, "yearly": 365, "quarterly": 90}
    days = period_map.get(billing_period, 30)
    doc = {
        "id": sid,
        "plan_id": sub_plan["id"],
        "plan_slug": sub_plan["slug"],
        "product_id": product["id"],
        "customer_email": email.lower(),
        "customer_id": customer["id"] if customer else None,
        "status": "active",
        "billing_period": billing_period,
        "price": price,
        "currency": currency,
        "seats": sub_plan.get("max_seats", 1),
        "current_period_start": now.isoformat(),
        "current_period_end": (now + timedelta(days=days)).isoformat(),
        "trial_start": None,
        "trial_end": None,
        "auto_renew": True,
        "canceled_at": None,
        "canceled_at_period_end": False,
        "cancellation_reason": None,
        "payment_provider": source,
        "payment_provider_subscription_id": provider_sub_id,
        "metadata": {},
        "notes": None,
        "source": source,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.subscriptions.insert_one(doc)
    await audit_log("webhook", None, None, "subscription.created",
                    "subscription", sid,
                    meta={"source": source, "product": product["slug"],
                          "email": email, "billing_period": billing_period,
                          "price": price})

    # Auto-provision a license for the subscription
    from crypto_core import generate_hmac_license, generate_rsa_license
    license_id = str(uuid.uuid4())
    if product["signing_method"] == "rsa":
        key = generate_rsa_license(license_id, product["slug"])
    else:
        secret = os.environ.get("HMAC_LICENSE_SECRET", "dev").encode()
        key = generate_hmac_license(license_id, product["slug"], secret)
    lic_doc = {
        "id": license_id,
        "key": key,
        "product_id": product["id"],
        "product_slug": product["slug"],
        "signing_method": product["signing_method"],
        "fingerprint_mode": product["fingerprint_mode"],
        "customer_email": email.lower(),
        "customer_id": customer["id"] if customer else None,
        "plan": f"sub:{sub_plan['slug']}",
        "seats": sub_plan.get("max_seats", 1),
        "expires_at": doc["current_period_end"],
        "notes": None,
        "status": "active",
        "source": source,
        "subscription_id": sid,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(lic_doc)
    await audit_log("webhook", None, None, "subscription.license_created",
                    "license", license_id,
                    meta={"subscription_id": sid, "product": product["slug"]})

    # Fire-and-forget email
    try:
        portal_url = (runtime_settings.get("CUSTOMER_PORTAL_URL")
                      or runtime_settings.get("APP_PUBLIC_URL").rstrip("/") + "/portal")
        subject, html = render_purchase_email(
            customer_email=email,
            license_key=key,
            product_name=product.get("name") or product["slug"],
            plan=f"sub:{sub_plan['slug']}",
            seats=sub_plan.get("max_seats", 1),
            source=source,
            portal_url=portal_url,
        )
        result = send_email(email, subject, html)
        await audit_log("system", None, None, "email.subscription_confirmation",
                        "subscription", sid,
                        severity="info" if result.get("sent") else "warning",
                        meta={"to": email, "provider": result.get("provider"),
                              "sent": result.get("sent", False)})
    except Exception as e:
        logger.exception("subscription confirmation email failed")

    return sid


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
        portal_url = (runtime_settings.get("CUSTOMER_PORTAL_URL")
                      or runtime_settings.get("APP_PUBLIC_URL").rstrip("/") + "/portal")
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
    secret = runtime_settings.get("LEMONSQUEEZY_WEBHOOK_SECRET")
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
    subscription_id = None
    if event_type in ("order_created", "subscription_created", "subscription_payment_success"):
        email = extract_email_lemonsqueezy(payload)
        product_slug = payload.get("meta", {}).get("custom_data", {}).get("product_slug")
        data = payload.get("data", {})
        attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
        if event_type.startswith("subscription_"):
            provider_sub_id = data.get("id")
            billing_period = "monthly"
            total = attrs.get("total", 0) or 0
            price = float(total) / 100 if total else 0
            subscription_id = await _provision_subscription(
                email, product_slug, plan="lemonsqueezy", source="lemonsqueezy",
                provider_sub_id=provider_sub_id, billing_period=billing_period,
                price=price, currency="USD")
        else:
            license_id = await _provision_license(email, product_slug, plan="lemonsqueezy",
                                                   source="lemonsqueezy")
    await _store_event("lemonsqueezy", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id, "subscription_id": subscription_id}


# ---------------- Paddle ----------------
@router.post("/paddle")
async def paddle(request: Request):
    body = await request.body()
    sig = request.headers.get("paddle-signature", "")
    secret = runtime_settings.get("PADDLE_WEBHOOK_SECRET")
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
    subscription_id = None
    if event_type in ("transaction.completed", "subscription.created", "subscription.activated"):
        email = extract_email_paddle(payload)
        d = payload.get("data") or {}
        product_slug = (d.get("custom_data") or {}).get("product_slug") if isinstance(d, dict) else None
        if event_type.startswith("subscription_"):
            provider_sub_id = d.get("id") if isinstance(d, dict) else None
            items = (d.get("items", []) if isinstance(d, dict) else [])
            price = 0
            billing_period = "monthly"
            if items and isinstance(items, list):
                first = items[0] if items else {}
                price_data = (first.get("price") or {}) if isinstance(first, dict) else {}
                unit_price = (price_data.get("unit_price") or {}) if isinstance(price_data, dict) else {}
                price = float(unit_price.get("amount", 0) or 0) / 100
                interval = (price_data.get("billing_cycle") or {}).get("interval", "month")
                billing_period = "monthly" if interval == "month" else "yearly" if interval == "year" else interval
            subscription_id = await _provision_subscription(
                email, product_slug, plan="paddle", source="paddle",
                provider_sub_id=provider_sub_id, billing_period=billing_period,
                price=price, currency="USD")
        else:
            license_id = await _provision_license(email, product_slug, plan="paddle", source="paddle")
    await _store_event("paddle", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id, "subscription_id": subscription_id}


# ---------------- Gumroad ----------------
@router.post("/gumroad")
async def gumroad(request: Request):
    body = await request.body()
    sig = request.headers.get("x-gumroad-signature", "")
    secret = runtime_settings.get("GUMROAD_WEBHOOK_SECRET")
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
    license_id = None
    subscription_id = None
    if event_type in ("subscription_created", "subscription_updated", "subscription_cancelled",
                      "subscription_restarted"):
        provider_sub_id = payload.get("subscription_id") or payload.get("id")
        price = float(payload.get("price", 0) or 0)
        billing_period = "monthly" if payload.get("subscription_duration") == "monthly" else \
                         "yearly" if payload.get("subscription_duration") == "yearly" else "monthly"
        subscription_id = await _provision_subscription(
            email, product_slug, plan="gumroad", source="gumroad",
            provider_sub_id=provider_sub_id, billing_period=billing_period,
            price=price, currency="USD")
    else:
        license_id = await _provision_license(email, product_slug, plan="gumroad", source="gumroad")
    await _store_event("gumroad", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id, "subscription_id": subscription_id}


# ---------------- Stripe ----------------
@router.post("/stripe")
async def stripe(request: Request):
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = runtime_settings.get("STRIPE_WEBHOOK_SECRET")
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
    subscription_id = None
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

        is_subscription_event = event_type == "customer.subscription.created" or \
            (event_type == "checkout.session.completed" and obj.get("mode") == "subscription") or \
            (event_type in ("invoice.paid", "invoice.payment_succeeded") and obj.get("subscription"))

        if is_subscription_event:
            provider_sub_id = obj.get("subscription") or obj.get("id")
            # For checkout/completed, the subscription ID is nested
            if event_type == "checkout.session.completed":
                provider_sub_id = obj.get("subscription")
            # For invoice events, the lines data has pricing
            billing_period = "monthly"
            price = 0
            lines = obj.get("lines", {}).get("data", []) if isinstance(obj.get("lines"), dict) else \
                    (obj.get("lines", []) if isinstance(obj.get("lines"), list) else [])
            if lines and isinstance(lines, list):
                first = lines[0] if lines else {}
                plan_data = first.get("plan") or {}
                interval = plan_data.get("interval", "month") if isinstance(plan_data, dict) else "month"
                billing_period = "monthly" if interval == "month" else "yearly" if interval == "year" else interval
                amount = first.get("amount", 0) or 0
                price = float(amount) / 100
            subscription_id = await _provision_subscription(
                email, product_slug, plan="stripe", source="stripe",
                provider_sub_id=provider_sub_id, billing_period=billing_period,
                price=price, currency="USD")
        else:
            license_id = await _provision_license(email, product_slug, plan="stripe", source="stripe")
    await _store_event("stripe", event_type, "processed", body, payload,
                       provider_event_id=provider_event_id, license_id=license_id)
    return {"ok": True, "license_id": license_id, "subscription_id": subscription_id}
