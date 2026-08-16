"""Subscription plans + subscriptions (admin + customer routes).
Coexists with the perpetual license matrix."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth import get_current_admin, get_current_customer, require_admin_role, _client_ip
from audit import log as audit_log
from db import db, now_iso, serialize_doc

router = APIRouter(tags=["subscriptions"])
admin_prefix = "/admin"
customer_prefix = "/customer"


# ── Pydantic models ──────────────────────────────────────────────────────────

class BillingOption(BaseModel):
    period: str = Field(pattern="^(monthly|yearly|quarterly)$")
    price: float = Field(gt=0)
    currency: str = "USD"


class SubscriptionPlanIn(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    product_id: str
    billing_options: list[BillingOption] = Field(min_length=1)
    features: list[str] = Field(default_factory=list)
    max_seats: int = 1
    max_activations: Optional[int] = None
    grace_days: int = 7
    trial_days: Optional[int] = None
    status: str = Field(default="active", pattern="^(active|archived)$")


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_options: Optional[list[BillingOption]] = None
    features: Optional[list[str]] = None
    max_seats: Optional[int] = None
    max_activations: Optional[int] = None
    grace_days: Optional[int] = None
    trial_days: Optional[int] = None
    status: Optional[str] = Field(default=None, pattern="^(active|archived)$")


# ── Admin: Subscription Plans CRUD ──────────────────────────────────────────

@router.get(f"{admin_prefix}/subscription-plans")
async def plans_list(admin=Depends(get_current_admin)):
    docs = await db.subscription_plans.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return serialize_doc(docs)


@router.post(f"{admin_prefix}/subscription-plans")
async def plans_create(body: SubscriptionPlanIn, request: Request,
                       admin=Depends(require_admin_role("admin"))):
    existing = await db.subscription_plans.find_one({"slug": body.slug})
    if existing:
        raise HTTPException(400, "Subscription plan slug already exists")
    product = await db.products.find_one({"id": body.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(400, "Invalid product_id")
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["product_slug"] = product["slug"]
    doc["created_at"] = now_iso()
    doc["updated_at"] = doc["created_at"]
    await db.subscription_plans.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "subscription_plan.create",
                    "subscription_plan", doc["id"], meta={"slug": body.slug},
                    ip=_client_ip(request))
    return serialize_doc(doc)


@router.put(f"{admin_prefix}/subscription-plans/{{pid}}")
async def plans_update(pid: str, body: SubscriptionPlanUpdate,
                       admin=Depends(require_admin_role("admin"))):
    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    update["updated_at"] = now_iso()
    res = await db.subscription_plans.find_one_and_update(
        {"id": pid}, {"$set": update}, return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "subscription_plan.update",
                    "subscription_plan", pid)
    return serialize_doc(res)


@router.delete(f"{admin_prefix}/subscription-plans/{{pid}}")
async def plans_archive(pid: str, admin=Depends(require_admin_role("admin"))):
    used = await db.subscriptions.count_documents({"plan_id": pid, "status": {"$ne": "expired"}})
    if used:
        raise HTTPException(400, f"Cannot archive: {used} active subscriptions use this plan")
    res = await db.subscription_plans.find_one_and_update(
        {"id": pid}, {"$set": {"status": "archived", "updated_at": now_iso()}},
        return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "subscription_plan.archive",
                    "subscription_plan", pid)
    return serialize_doc(res)


# ── Admin: Subscriptions ─────────────────────────────────────────────────────

@router.get(f"{admin_prefix}/subscriptions")
async def subscriptions_list(admin=Depends(get_current_admin),
                             status: Optional[str] = None,
                             plan_id: Optional[str] = None,
                             q: Optional[str] = None,
                             limit: int = 200):
    query = {}
    if status:
        query["status"] = status
    if plan_id:
        query["plan_id"] = plan_id
    if q:
        query["$or"] = [
            {"customer_email": {"$regex": q, "$options": "i"}},
            {"plan_slug": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.subscriptions.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for d in docs:
        d["licenses_count"] = await db.licenses.count_documents({"subscription_id": d["id"]})
        d["activations_count"] = await db.activations.count_documents(
            {"license_id": {"$in": [
                lic["id"] async for lic in db.licenses.find(
                    {"subscription_id": d["id"]}, {"id": 1})]},
             "status": "active"})
    return serialize_doc(docs)


@router.get(f"{admin_prefix}/subscriptions/{{sid}}")
async def subscription_detail(sid: str, admin=Depends(get_current_admin)):
    sub = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    licenses = await db.licenses.find({"subscription_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for lic in licenses:
        lic["activations_count"] = await db.activations.count_documents(
            {"license_id": lic["id"], "status": "active"})
    plan = await db.subscription_plans.find_one({"id": sub["plan_id"]}, {"_id": 0})
    audits = await db.audit_log.find({"target_type": "subscription", "target_id": sid},
                                     {"_id": 0}).sort("ts", -1).to_list(200)
    return {
        "subscription": serialize_doc(sub),
        "plan": serialize_doc(plan) if plan else None,
        "licenses": serialize_doc(licenses),
        "audit": serialize_doc(audits),
    }


class SubscriptionCancelIn(BaseModel):
    at_period_end: bool = True
    reason: Optional[str] = None


@router.post(f"{admin_prefix}/subscriptions/{{sid}}/cancel")
async def subscription_cancel(sid: str, body: SubscriptionCancelIn,
                              request: Request, admin=Depends(require_admin_role("admin"))):
    sub = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    if sub["status"] in ("canceled", "expired"):
        raise HTTPException(400, f"Subscription is already {sub['status']}")
    update = {
        "status": "canceled" if not body.at_period_end else "active",
        "canceled_at": now_iso(),
        "canceled_at_period_end": body.at_period_end,
        "auto_renew": False,
        "updated_at": now_iso(),
    }
    if body.reason:
        update["cancellation_reason"] = body.reason
    if not body.at_period_end:
        update["current_period_end"] = now_iso()
        await db.licenses.update_many(
            {"subscription_id": sid, "status": "active"},
            {"$set": {"status": "expired", "updated_at": now_iso()}})
        await db.activations.update_many(
            {"license_id": {"$in": [l["id"] async for l in db.licenses.find(
                {"subscription_id": sid}, {"id": 1})]},
             "status": "active"},
            {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                      "deactivated_reason": "subscription_canceled"}})
    await db.subscriptions.update_one({"id": sid}, {"$set": update})
    await audit_log("admin", admin["id"], admin["email"], "subscription.cancel",
                    "subscription", sid, severity="warning",
                    meta={"at_period_end": body.at_period_end,
                          "reason": body.reason},
                    ip=_client_ip(request))
    fresh = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    return serialize_doc(fresh)


@router.post(f"{admin_prefix}/subscriptions/{{sid}}/reactivate")
async def subscription_reactivate(sid: str, request: Request,
                                   admin=Depends(require_admin_role("admin"))):
    sub = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    if sub["status"] != "canceled":
        raise HTTPException(400, "Only canceled subscriptions can be reactivated")
    if not sub.get("canceled_at_period_end"):
        raise HTTPException(400, "Cannot reactivate an immediately-canceled subscription")
    update = {
        "canceled_at": None,
        "canceled_at_period_end": False,
        "cancellation_reason": None,
        "auto_renew": True,
        "status": "active",
        "updated_at": now_iso(),
    }
    await db.subscriptions.update_one({"id": sid}, {"$set": update})
    await audit_log("admin", admin["id"], admin["email"], "subscription.reactivate",
                    "subscription", sid, severity="info",
                    ip=_client_ip(request))
    fresh = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    return serialize_doc(fresh)


class SubscriptionChangePlanIn(BaseModel):
    plan_id: str
    billing_period: str = Field(pattern="^(monthly|yearly|quarterly)$")


@router.post(f"{admin_prefix}/subscriptions/{{sid}}/change-plan")
async def subscription_change_plan(sid: str, body: SubscriptionChangePlanIn,
                                    request: Request,
                                    admin=Depends(require_admin_role("admin"))):
    sub = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    new_plan = await db.subscription_plans.find_one({"id": body.plan_id}, {"_id": 0})
    if not new_plan:
        raise HTTPException(400, "Invalid plan_id")
    matching = [bo for bo in new_plan.get("billing_options", [])
                if bo["period"] == body.billing_period]
    if not matching:
        raise HTTPException(400,
                            f"Plan '{new_plan['slug']}' does not offer {body.billing_period} billing")
    bo = matching[0]
    update = {
        "plan_id": body.plan_id,
        "plan_slug": new_plan["slug"],
        "billing_period": body.billing_period,
        "price": bo["price"],
        "currency": bo["currency"],
        "seats": new_plan.get("max_seats", sub.get("seats", 1)),
        "updated_at": now_iso(),
    }
    await db.subscriptions.update_one({"id": sid}, {"$set": update})
    await audit_log("admin", admin["id"], admin["email"], "subscription.change_plan",
                    "subscription", sid, severity="info",
                    meta={"from_plan": sub.get("plan_slug"),
                          "to_plan": new_plan["slug"],
                          "billing_period": body.billing_period},
                    ip=_client_ip(request))
    fresh = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    return serialize_doc(fresh)


class SubscriptionAddLicenseIn(BaseModel):
    seats: int = 1
    notes: Optional[str] = None


@router.post(f"{admin_prefix}/subscriptions/{{sid}}/add-license")
async def subscription_add_license(sid: str, body: SubscriptionAddLicenseIn,
                                    request: Request,
                                    admin=Depends(require_admin_role("admin"))):
    from crypto_core import generate_license_key
    sub = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Subscription not found")
    product = await db.products.find_one({"id": sub["product_id"]}, {"_id": 0})
    if not product:
        raise HTTPException(400, "Linked product not found")
    license_id = str(uuid.uuid4())
    key = generate_license_key(sub.get("plan_slug", "standard"))
    doc = {
        "id": license_id,
        "key": key,
        "product_id": product["id"],
        "product_slug": product["slug"],
        "signing_method": "short",
        "fingerprint_mode": product["fingerprint_mode"],
        "customer_email": sub["customer_email"],
        "customer_id": sub.get("customer_id"),
        "plan": f"sub:{sub['plan_slug']}",
        "seats": body.seats,
        "expires_at": sub.get("current_period_end"),
        "notes": body.notes,
        "status": "active",
        "source": "subscription",
        "subscription_id": sid,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "subscription.add_license",
                    "license", license_id, severity="info",
                    meta={"subscription_id": sid, "seats": body.seats},
                    ip=_client_ip(request))
    return serialize_doc(doc)


async def _subscription_sync_licenses(sub: dict) -> None:
    """Sync license statuses to match subscription status.
    Called by integrate/validate and webhook handlers."""
    target_status = "active" if sub["status"] == "active" else "expired"
    await db.licenses.update_many(
        {"subscription_id": sub["id"], "status": {"$ne": target_status}},
        {"$set": {"status": target_status, "updated_at": now_iso()}})
    if target_status != "active":
        await db.activations.update_many(
            {"license_id": {"$in": [l["id"] async for l in db.licenses.find(
                {"subscription_id": sub["id"]}, {"id": 1})]},
             "status": "active"},
            {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                      "deactivated_reason": f"subscription_{sub['status']}"}})
    # Update license expiry to match subscription period
    if sub.get("current_period_end") and sub["status"] == "active":
        await db.licenses.update_many(
            {"subscription_id": sub["id"]},
            {"$set": {"expires_at": sub["current_period_end"],
                      "updated_at": now_iso()}})


async def resolve_subscription_status(sub: dict) -> dict:
    """Evaluate a subscription's current status and auto-expire if past due.
    Returns the subscription dict (possibly updated)."""
    now = datetime.now(timezone.utc)
    if sub["status"] in ("expired", "canceled"):
        return sub
    period_end = sub.get("current_period_end")
    if period_end:
        try:
            end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt < now and sub["status"] == "past_due":
                sub["status"] = "expired"
                await db.subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$set": {"status": "expired", "updated_at": now_iso()}})
                await _subscription_sync_licenses(sub)
            elif end_dt < now and sub["status"] == "active" and not sub.get("auto_renew"):
                sub["status"] = "expired"
                await db.subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$set": {"status": "expired", "updated_at": now_iso()}})
                await _subscription_sync_licenses(sub)
            elif end_dt < now and sub["status"] == "active":
                sub["status"] = "past_due"
                await db.subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$set": {"status": "past_due", "updated_at": now_iso()}})
        except ValueError:
            pass
    return sub


# ── Customer: Subscriptions ──────────────────────────────────────────────────

@router.get(f"{customer_prefix}/subscriptions")
async def my_subscriptions(customer=Depends(get_current_customer)):
    docs = await db.subscriptions.find(
        {"customer_email": customer["email"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    out = []
    for sub in docs:
        sub = await resolve_subscription_status(sub)
        sub["licenses_count"] = await db.licenses.count_documents(
            {"subscription_id": sub["id"]})
        sub["activations_count"] = await db.activations.count_documents(
            {"license_id": {"$in": [l["id"] async for l in db.licenses.find(
                {"subscription_id": sub["id"]}, {"id": 1})]},
             "status": "active"})
        plan = await db.subscription_plans.find_one(
            {"id": sub["plan_id"]}, {"_id": 0, "billing_options": 0})
        sub["plan"] = serialize_doc(plan) if plan else None
        out.append(serialize_doc(sub))
    return out


@router.get(f"{customer_prefix}/subscriptions/{{sid}}")
async def my_subscription_detail(sid: str, customer=Depends(get_current_customer)):
    sub = await db.subscriptions.find_one(
        {"id": sid, "customer_email": customer["email"]}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    sub = await resolve_subscription_status(sub)
    licenses = await db.licenses.find(
        {"subscription_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for lic in licenses:
        lic["activations_count"] = await db.activations.count_documents(
            {"license_id": lic["id"], "status": "active"})
    plan = await db.subscription_plans.find_one(
        {"id": sub["plan_id"]}, {"_id": 0})
    return {
        "subscription": serialize_doc(sub),
        "plan": serialize_doc(plan) if plan else None,
        "licenses": serialize_doc(licenses),
    }


@router.post(f"{customer_prefix}/subscriptions/{{sid}}/cancel")
async def my_subscription_cancel(sid: str, body: SubscriptionCancelIn,
                                  customer=Depends(get_current_customer)):
    sub = await db.subscriptions.find_one(
        {"id": sid, "customer_email": customer["email"]}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Not found")
    if sub["status"] in ("canceled", "expired"):
        raise HTTPException(400, f"Already {sub['status']}")
    update = {
        "canceled_at": now_iso(),
        "canceled_at_period_end": body.at_period_end,
        "auto_renew": False,
        "updated_at": now_iso(),
    }
    if body.reason:
        update["cancellation_reason"] = body.reason
    if not body.at_period_end:
        update["status"] = "canceled"
        update["current_period_end"] = now_iso()
        await _subscription_sync_licenses({**sub, **update})
    await db.subscriptions.update_one({"id": sid}, {"$set": update})
    await audit_log("customer", customer["id"], customer["email"],
                    "subscription.cancel", "subscription", sid, severity="warning",
                    meta={"at_period_end": body.at_period_end})
    fresh = await db.subscriptions.find_one({"id": sid}, {"_id": 0})
    return serialize_doc(fresh)
