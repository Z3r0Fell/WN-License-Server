"""Purchase portal (in-house checkout) routes.

A buyer picks Pro / Ultra on the public /checkout page, drops their email,
and a *pending order* is recorded here. The buyer pays admin directly
(e-transfer / PayPal to admin@watchnexus.ca) and the admin marks the order
as PAID from the admin dashboard — that marks the order paid, issues the
short serial via the normal license pipeline, and emails it to the buyer.

This keeps the flow payment-provider-free today while leaving the order
records in place so Stripe / PayPal can be layered in later behind the same
mark-paid path (webhooks would just call the same fulfill function).
"""
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from audit import log as audit_log
from auth import get_current_admin, require_admin_role
from db import db, now_iso, serialize_doc
import runtime_settings

router = APIRouter(tags=["orders"])
admin_prefix = "/admin"

ORDER_STATUSES = ("pending_payment", "paid", "canceled")


def _client_ip(request: Request) -> Optional[str]:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _plan_info(plan: str) -> Optional[dict]:
    """Plan metadata. Prices default to the CAD one-time prices but are
    overridable from the admin Settings UI (checkout category)."""
    p = (plan or "").strip().lower()
    if p == "pro":
        return {
            "plan": "pro",
            "name": "WatchNexus Pro",
            "tier": "PRO",
            "product_slug": "watchnexus-pro",
            "price_cad": float(runtime_settings.get("CHECKOUT_PRO_PRICE_CAD", "35")),
            "seats": 1,
        }
    if p == "ultra":
        return {
            "plan": "ultra",
            "name": "WatchNexus Ultra",
            "tier": "ULT",
            "product_slug": "watchnexus-pro",
            "price_cad": float(runtime_settings.get("CHECKOUT_ULTRA_PRICE_CAD", "60")),
            "seats": 1,
        }
    return None


def _new_reference() -> str:
    return "ORD-" + secrets.token_hex(5).upper()


def _payment_email() -> str:
    return runtime_settings.get("CHECKOUT_PAYMENT_EMAIL", "admin@watchnexus.ca")


# ── Public (no auth): plans + order creation + status lookup ─────────────────

@router.get("/orders/plans")
async def orders_plans():
    """Public catalog for the checkout page (prices, payment destination)."""
    out = []
    for plan in ("pro", "ultra"):
        info = _plan_info(plan)
        out.append({
            "plan": info["plan"],
            "name": info["name"],
            "tier": info["tier"],
            "price_cad": info["price_cad"],
            "currency": "CAD",
            "seats": info["seats"],
            "one_time": True,
        })
    return {
        "plans": out,
        "payment_email": _payment_email(),
        "payment_methods": runtime_settings.get(
            "CHECKOUT_PAYMENT_METHODS", "Interac e-Transfer (Canada) or PayPal"),
    }


class OrderCreateIn(BaseModel):
    plan: str = Field(pattern="^(pro|ultra)$")
    email: EmailStr
    buyer_name: Optional[str] = Field(None, max_length=120)


@router.post("/orders")
async def orders_create(body: OrderCreateIn, request: Request):
    """Create a pending order for a one-time license purchase."""
    info = _plan_info(body.plan)
    if not info:
        raise HTTPException(400, "Unsupported plan")
    order_id = str(uuid.uuid4())
    doc = {
        "id": order_id,
        "reference": _new_reference(),
        "plan": info["plan"],
        "plan_name": info["name"],
        "tier": info["tier"],
        "product_slug": info["product_slug"],
        "price_cad": info["price_cad"],
        "currency": "CAD",
        "seats": info["seats"],
        "email": str(body.email).lower(),
        "buyer_name": body.buyer_name,
        "status": "pending_payment",
        "created_at": now_iso(),
        "paid_at": None,
        "canceled_at": None,
        "license_id": None,
        "license_key": None,
        "notes": None,
        "fulfilled_by": None,
        "fulfilled_at": None,
        "updated_at": now_iso(),
    }
    await db.orders.insert_one(doc)
    await audit_log("system", None, body.email.lower(), "order.create",
                    "order", order_id,
                    meta={"plan": info["plan"], "price_cad": info["price_cad"]},
                    severity="info", ip=_client_ip(request))
    return {
        **serialize_doc(doc),
        "payment_email": _payment_email(),
        "payment_instructions": runtime_settings.get(
            "CHECKOUT_PAYMENT_INSTRUCTIONS",
            "Pay the exact amount to the address above via Interac e-Transfer "
            "(Canada) or PayPal. Include your order reference in the message. "
            "Once payment is confirmed, your WatchNexus serial will be emailed "
            "to the address you provided."),
    }


@router.get("/orders/{ref}")
async def orders_lookup(ref: str):
    """Public order status lookup by reference (unguessable code)."""
    order = await db.orders.find_one({"reference": ref.strip().upper()}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    return serialize_doc(order)


# ── Stripe Checkout (additional payment option) ──────────────────────────────

@router.post("/orders/{ref}/stripe-checkout")
async def order_stripe_checkout(ref: str, request: Request):
    """Create a Stripe Checkout Session for an order and return its hosted URL.

    The buyer is redirected to checkout.stripe.com; on success Stripe fires
    `checkout.session.completed` to /api/webhooks/stripe, which matches the
    order via metadata and calls the same fulfill path as manual mark-paid."""
    import requests

    secret = runtime_settings.get("STRIPE_SECRET_KEY")
    if not secret or not secret.startswith(("sk_", "rk_")):
        raise HTTPException(503, "Stripe checkout is not configured yet")

    order = await db.orders.find_one({"reference": ref.strip().upper()}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] != "pending_payment":
        raise HTTPException(400, f"Order is {order['status']} - cannot pay for it")

    public_url = (runtime_settings.get("APP_PUBLIC_URL")
                  or "https://licenses.watchnexus.ca").rstrip("/")
    amount_cents = int(round(float(order.get("price_cad", 0)) * 100))

    data = {
        "mode": "payment",
        "customer_email": order["email"],
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": order.get("currency", "cad").lower(),
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][price_data][product_data][name]": order.get("plan_name", "WatchNexus"),
        "success_url": f"{public_url}/checkout?ref={order['reference']}&status=paid",
        "cancel_url": f"{public_url}/checkout?ref={order['reference']}&status=canceled",
        "metadata[order_ref]": order["reference"],
        "metadata[plan]": order["plan"],
    }
    try:
        r = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(secret, ""),
            data=data,
            timeout=20,
        )
    except Exception as e:
        raise HTTPException(502, f"Stripe request failed: {e}")
    if r.status_code != 200:
        raise HTTPException(502, f"Stripe error {r.status_code}: {r.text[:300]}")

    sess = r.json()
    await audit_log("system", None, order["email"], "order.stripe_checkout",
                    "order", order["id"],
                    meta={"reference": order["reference"],
                          "stripe_session": sess.get("id")},
                    severity="info", ip=_client_ip(request))
    return {"url": sess["url"], "session_id": sess["id"]}



# ── Admin: list + fulfill (mark paid -> issue serial + email) ────────────────

@router.get(f"{admin_prefix}/orders")
async def orders_list(admin=Depends(get_current_admin),
                      status: Optional[str] = None,
                      q: Optional[str] = None,
                      limit: int = 200):
    query = {}
    if status:
        if status not in ORDER_STATUSES:
            raise HTTPException(400, f"status must be one of {ORDER_STATUSES}")
        query["status"] = status
    if q:
        query["$or"] = [
            {"reference": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"buyer_name": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return serialize_doc(docs)


class OrderMarkPaidIn(BaseModel):
    notes: Optional[str] = None


async def _fulfill_order(order: dict, notes: Optional[str],
                         actor_email: str) -> dict:
    """Shared fulfill path: issue the serial + email it, mark order paid.

    Also used by future Stripe / PayPal webhooks so checkout and payment
    providers converge on the same issuance logic."""
    if order["status"] == "paid":
        return order
    if order["status"] != "pending_payment":
        raise HTTPException(400, f"Order is {order['status']} - cannot mark paid")

    from routers.admin import _create_license

    product = await db.products.find_one({"slug": order["product_slug"]}, {"_id": 0})
    if not product:
        product = await db.products.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    if not product:
        raise HTTPException(400, "No product configured to issue a license against")

    lic = await _create_license(
        product_id=product["id"],
        customer_email=order["email"],
        plan=order["plan"],
        seats=order.get("seats", 1),
        expires_at=None,
        notes=notes or order.get("notes"),
        source="checkout",
    )
    update = {
        "status": "paid",
        "paid_at": now_iso(),
        "license_id": lic["id"],
        "license_key": lic["key"],
        "fulfilled_by": actor_email,
        "fulfilled_at": now_iso(),
        "updated_at": now_iso(),
    }
    if notes:
        update["notes"] = notes
    await db.orders.update_one({"id": order["id"]}, {"$set": update})
    return {**order, **update}


@router.post(f"{admin_prefix}/orders/{{oid}}/mark-paid")
async def order_mark_paid(oid: str, body: OrderMarkPaidIn, request: Request,
                          admin=Depends(require_admin_role("admin"))):
    """Confirm payment: issues the serial via the normal pipeline (which emails
    it) and marks the order PAID."""
    order = await db.orders.find_one({"id": oid}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    fulfilled = await _fulfill_order(order, body.notes, admin.get("email"))
    await audit_log("admin", admin["id"], admin["email"], "order.mark_paid",
                    "order", oid,
                    meta={"plan": order["plan"], "email": order["email"],
                          "license_id": fulfilled.get("license_id"),
                          "reference": order["reference"]},
                    severity="warning", ip=_client_ip(request))
    return serialize_doc(fulfilled)


@router.post(f"{admin_prefix}/orders/{{oid}}/cancel")
async def order_cancel(oid: str, request: Request,
                       admin=Depends(require_admin_role("admin"))):
    """Cancel a pending order (e.g. payment never arrived / duplicate)."""
    order = await db.orders.find_one({"id": oid}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] == "paid":
        raise HTTPException(400, "Cannot cancel a paid order - revoke the license instead")
    if order["status"] == "canceled":
        return {"ok": True, "already_canceled": True}
    await db.orders.update_one(
        {"id": oid},
        {"$set": {"status": "canceled", "canceled_at": now_iso(), "updated_at": now_iso()}},
    )
    await audit_log("admin", admin["id"], admin["email"], "order.cancel",
                    "order", oid, severity="warning",
                    meta={"reference": order["reference"], "email": order["email"]},
                    ip=_client_ip(request))
    return {"ok": True}


@router.post(f"{admin_prefix}/orders/{{oid}}/resend-email")
async def order_resend_email(oid: str, request: Request,
                             admin=Depends(require_admin_role("admin"))):
    """Re-send the serial email for an already-paid order."""
    order = await db.orders.find_one({"id": oid}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] != "paid":
        raise HTTPException(400, "Only paid orders have a serial to resend")
    lic = await db.licenses.find_one({"id": order["license_id"]}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "Linked license not found")

    from email_sender import render_purchase_email, send_email
    product = await db.products.find_one({"id": lic["product_id"]}, {"_id": 0})
    portal_url = (runtime_settings.get("CUSTOMER_PORTAL_URL")
                  or runtime_settings.get("APP_PUBLIC_URL").rstrip("/") + "/portal")
    subject, html = render_purchase_email(
        customer_email=order["email"],
        license_key=lic["key"],
        product_name=(product.get("name") if product else None) or lic["product_slug"],
        plan=lic["plan"],
        seats=lic["seats"],
        source="checkout",
        portal_url=portal_url,
    )
    result = send_email(order["email"], subject, html)
    await audit_log("admin", admin["id"], admin["email"], "order.resend_email",
                    "order", oid, meta={"to": order["email"],
                                        "sent": result.get("sent", False),
                                        "provider": result.get("provider")},
                    ip=_client_ip(request))
    return result
