"""Admin routes: login, products, licenses, activations, customers, audit, api keys, builds, webhooks list, dashboard."""
import csv
import io
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, EmailStr, Field

from auth import (get_current_admin, hash_password, verify_password,
                  issue_session_token)
from audit import log as audit_log
from crypto_core import (generate_hmac_license, generate_rsa_license,
                         get_rsa_public_pem)
from db import db, now_iso, serialize_doc

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------- Auth --------------------
class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def admin_login(body: AdminLoginIn, request: Request):
    user = await db.admin_users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = issue_session_token(user["id"], "admin", user["email"])
    await audit_log("admin", user["id"], user["email"], "admin.login",
                    severity="info", ip=request.client.host if request.client else None)
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name")}}


@router.get("/me")
async def admin_me(admin=Depends(get_current_admin)):
    return {"id": admin["id"], "email": admin["email"], "name": admin.get("name")}


# -------------------- Dashboard --------------------
@router.get("/dashboard")
async def dashboard(admin=Depends(get_current_admin)):
    total = await db.licenses.count_documents({})
    active = await db.licenses.count_documents({"status": "active"})
    revoked = await db.licenses.count_documents({"status": "revoked"})
    expired = await db.licenses.count_documents({"status": "expired"})
    activations = await db.activations.count_documents({"status": "active"})
    customers = await db.customers.count_documents({})
    products = await db.products.count_documents({})
    recent_acts = await db.activations.find({}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)
    recent_audit = await db.audit_log.find({}, {"_id": 0}).sort("ts", -1).limit(8).to_list(8)
    recent_webhooks = await db.webhook_events.find({}, {"_id": 0}).sort("received_at", -1).limit(8).to_list(8)
    return {
        "licenses_total": total,
        "licenses_active": active,
        "licenses_revoked": revoked,
        "licenses_expired": expired,
        "active_installs": activations,
        "customers_total": customers,
        "products_total": products,
        "recent_activations": serialize_doc(recent_acts),
        "recent_audit": serialize_doc(recent_audit),
        "recent_webhooks": serialize_doc(recent_webhooks),
    }


# -------------------- Products --------------------
class ProductIn(BaseModel):
    name: str
    slug: str
    signing_method: str = Field("hmac", pattern="^(hmac|rsa)$")
    fingerprint_mode: str = Field("both", pattern="^(none|hw|domain|both)$")
    max_seats_default: int = 1
    description: Optional[str] = None


@router.get("/products")
async def products_list(admin=Depends(get_current_admin)):
    docs = await db.products.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return serialize_doc(docs)


@router.post("/products")
async def products_create(body: ProductIn, request: Request, admin=Depends(get_current_admin)):
    existing = await db.products.find_one({"slug": body.slug})
    if existing:
        raise HTTPException(400, "Product slug already exists")
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = now_iso()
    doc["updated_at"] = doc["created_at"]
    await db.products.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "product.create",
                    "product", doc["id"], meta={"slug": body.slug},
                    ip=request.client.host if request.client else None)
    return serialize_doc(doc)


@router.put("/products/{pid}")
async def products_update(pid: str, body: ProductIn, admin=Depends(get_current_admin)):
    update = body.model_dump()
    update["updated_at"] = now_iso()
    res = await db.products.find_one_and_update(
        {"id": pid}, {"$set": update}, return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "product.update", "product", pid)
    return serialize_doc(res)


@router.delete("/products/{pid}")
async def products_delete(pid: str, admin=Depends(get_current_admin)):
    used = await db.licenses.count_documents({"product_id": pid})
    if used:
        raise HTTPException(400, f"Cannot delete: {used} licenses use this product")
    await db.products.delete_one({"id": pid})
    await audit_log("admin", admin["id"], admin["email"], "product.delete", "product", pid)
    return {"ok": True}


# -------------------- Licenses --------------------
class LicenseIn(BaseModel):
    product_id: str
    customer_email: Optional[EmailStr] = None
    plan: str = "standard"
    seats: int = 1
    expires_at: Optional[str] = None  # ISO
    notes: Optional[str] = None


async def _create_license(product_id: str, customer_email: Optional[str],
                          plan: str, seats: int, expires_at: Optional[str],
                          notes: Optional[str], source: str = "admin") -> dict:
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(400, "Invalid product_id")
    license_id = str(uuid.uuid4())
    if product["signing_method"] == "rsa":
        key = generate_rsa_license(license_id, product["slug"])
    else:
        secret = os.environ.get("HMAC_LICENSE_SECRET", "dev").encode()
        key = generate_hmac_license(license_id, product["slug"], secret)
    customer_id = None
    if customer_email:
        c = await db.customers.find_one({"email": customer_email.lower()}, {"_id": 0})
        if c:
            customer_id = c["id"]
    doc = {
        "id": license_id,
        "key": key,
        "product_id": product_id,
        "product_slug": product["slug"],
        "signing_method": product["signing_method"],
        "fingerprint_mode": product["fingerprint_mode"],
        "customer_email": customer_email.lower() if customer_email else None,
        "customer_id": customer_id,
        "plan": plan,
        "seats": seats,
        "expires_at": expires_at,
        "notes": notes,
        "status": "active",
        "source": source,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.licenses.insert_one(doc)
    return doc


@router.get("/licenses")
async def licenses_list(admin=Depends(get_current_admin),
                        status: Optional[str] = None,
                        product_id: Optional[str] = None,
                        q: Optional[str] = None,
                        limit: int = 200):
    query = {}
    if status:
        query["status"] = status
    if product_id:
        query["product_id"] = product_id
    if q:
        query["$or"] = [
            {"key": {"$regex": q, "$options": "i"}},
            {"customer_email": {"$regex": q, "$options": "i"}},
            {"plan": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.licenses.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    # attach activation count
    for d in docs:
        d["activations_count"] = await db.activations.count_documents(
            {"license_id": d["id"], "status": "active"})
    return serialize_doc(docs)


@router.post("/licenses")
async def licenses_create(body: LicenseIn, request: Request, admin=Depends(get_current_admin)):
    doc = await _create_license(body.product_id, body.customer_email, body.plan,
                                body.seats, body.expires_at, body.notes, source="admin")
    await audit_log("admin", admin["id"], admin["email"], "license.create",
                    "license", doc["id"], meta={"product": doc["product_slug"]},
                    ip=request.client.host if request.client else None)
    return serialize_doc(doc)


@router.get("/licenses/{lid}")
async def license_detail(lid: str, admin=Depends(get_current_admin)):
    lic = await db.licenses.find_one({"id": lid}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "Not found")
    activations = await db.activations.find({"license_id": lid}, {"_id": 0}).sort("created_at", -1).to_list(500)
    audits = await db.audit_log.find({"target_type": "license", "target_id": lid}, {"_id": 0}).sort("ts", -1).to_list(200)
    return {
        "license": serialize_doc(lic),
        "activations": serialize_doc(activations),
        "audit": serialize_doc(audits),
    }


class LicenseUpdate(BaseModel):
    seats: Optional[int] = None
    expires_at: Optional[str] = None
    plan: Optional[str] = None
    notes: Optional[str] = None
    customer_email: Optional[EmailStr] = None


@router.patch("/licenses/{lid}")
async def license_update(lid: str, body: LicenseUpdate, admin=Depends(get_current_admin)):
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields to update")
    payload["updated_at"] = now_iso()
    if "customer_email" in payload:
        payload["customer_email"] = payload["customer_email"].lower()
    res = await db.licenses.find_one_and_update({"id": lid}, {"$set": payload},
                                                return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "license.update", "license", lid, meta=payload)
    return serialize_doc(res)


@router.post("/licenses/{lid}/revoke")
async def license_revoke(lid: str, admin=Depends(get_current_admin)):
    res = await db.licenses.update_one({"id": lid}, {"$set": {"status": "revoked", "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await db.activations.update_many({"license_id": lid, "status": "active"},
                                     {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                                               "deactivated_reason": "license_revoked"}})
    await audit_log("admin", admin["id"], admin["email"], "license.revoke", "license", lid, severity="warning")
    return {"ok": True}


@router.post("/licenses/{lid}/extend")
async def license_extend(lid: str, body: dict, admin=Depends(get_current_admin)):
    new_expiry = body.get("expires_at")
    if not new_expiry:
        raise HTTPException(400, "expires_at required (ISO timestamp)")
    res = await db.licenses.update_one({"id": lid},
                                       {"$set": {"expires_at": new_expiry, "status": "active",
                                                 "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "license.extend", "license", lid,
                    meta={"expires_at": new_expiry})
    return {"ok": True}


@router.post("/licenses/{lid}/activations/{aid}/deactivate")
async def license_deactivate_install(lid: str, aid: str, admin=Depends(get_current_admin)):
    res = await db.activations.update_one(
        {"id": aid, "license_id": lid, "status": "active"},
        {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                  "deactivated_reason": "admin_action"}})
    if not res.matched_count:
        raise HTTPException(404, "Activation not found or already inactive")
    await audit_log("admin", admin["id"], admin["email"], "activation.deactivate",
                    "activation", aid, severity="warning", meta={"license_id": lid})
    return {"ok": True}


@router.post("/licenses/bulk-import")
async def licenses_bulk_import(file: UploadFile = File(...),
                                admin=Depends(get_current_admin)):
    content = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    results = []
    created = 0
    failed = 0
    for i, row in enumerate(reader, start=1):
        try:
            product_slug = (row.get("product_slug") or "").strip()
            product = await db.products.find_one({"slug": product_slug}, {"_id": 0})
            if not product:
                raise ValueError(f"product_slug '{product_slug}' not found")
            email = (row.get("customer_email") or "").strip() or None
            plan = (row.get("plan") or "standard").strip()
            seats = int(row.get("seats") or 1)
            expires_at = (row.get("expires_at") or "").strip() or None
            notes = (row.get("notes") or "").strip() or None
            doc = await _create_license(product["id"], email, plan, seats,
                                        expires_at, notes, source="bulk_import")
            results.append({"row": i, "ok": True, "license_id": doc["id"], "key": doc["key"]})
            created += 1
        except Exception as e:
            results.append({"row": i, "ok": False, "error": str(e)})
            failed += 1
    await audit_log("admin", admin["id"], admin["email"], "license.bulk_import",
                    severity="info", meta={"created": created, "failed": failed})
    return {"created": created, "failed": failed, "results": results}


# -------------------- Customers --------------------
@router.get("/customers")
async def customers_list(admin=Depends(get_current_admin), limit: int = 200):
    docs = await db.customers.find({}, {"_id": 0, "password_hash": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    for d in docs:
        d["licenses_count"] = await db.licenses.count_documents({"customer_email": d["email"]})
    return serialize_doc(docs)


# -------------------- API keys --------------------
class ApiKeyIn(BaseModel):
    name: str
    product_id: Optional[str] = None
    scopes: list[str] = Field(default_factory=lambda: ["activate", "validate", "deactivate"])


@router.get("/api-keys")
async def api_keys_list(admin=Depends(get_current_admin)):
    docs = await db.api_keys.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    # mask key
    for d in docs:
        k = d.get("key", "")
        d["key_masked"] = (k[:8] + "\u2026" + k[-4:]) if k else ""
        d.pop("key", None)
    return serialize_doc(docs)


@router.post("/api-keys")
async def api_keys_create(body: ApiKeyIn, admin=Depends(get_current_admin)):
    raw = "wnk_" + secrets.token_urlsafe(32)
    doc = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "product_id": body.product_id,
        "scopes": body.scopes,
        "key": raw,
        "status": "active",
        "created_at": now_iso(),
        "last_used_at": None,
    }
    await db.api_keys.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "api_key.create",
                    "api_key", doc["id"], severity="warning")
    return {"id": doc["id"], "name": doc["name"], "key": raw, "created_at": doc["created_at"],
            "product_id": doc["product_id"], "scopes": doc["scopes"], "status": doc["status"]}


@router.post("/api-keys/{kid}/revoke")
async def api_keys_revoke(kid: str, admin=Depends(get_current_admin)):
    res = await db.api_keys.update_one({"id": kid}, {"$set": {"status": "revoked"}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "api_key.revoke", "api_key", kid, severity="warning")
    return {"ok": True}


# -------------------- Builds --------------------
class BuildIn(BaseModel):
    product_id: str
    version: str
    download_url: str
    notes: Optional[str] = None


@router.get("/builds")
async def builds_list(admin=Depends(get_current_admin)):
    docs = await db.builds.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return serialize_doc(docs)


@router.post("/builds")
async def builds_create(body: BuildIn, admin=Depends(get_current_admin)):
    product = await db.products.find_one({"id": body.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(400, "Invalid product_id")
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["product_slug"] = product["slug"]
    doc["created_at"] = now_iso()
    await db.builds.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "build.create", "build", doc["id"])
    return serialize_doc(doc)


@router.delete("/builds/{bid}")
async def builds_delete(bid: str, admin=Depends(get_current_admin)):
    await db.builds.delete_one({"id": bid})
    await audit_log("admin", admin["id"], admin["email"], "build.delete", "build", bid)
    return {"ok": True}


# -------------------- Webhook events --------------------
@router.get("/webhook-events")
async def webhook_events_list(admin=Depends(get_current_admin), limit: int = 200):
    docs = await db.webhook_events.find({}, {"_id": 0}).sort("received_at", -1).limit(limit).to_list(limit)
    return serialize_doc(docs)


@router.get("/webhook-events/{eid}")
async def webhook_event_detail(eid: str, admin=Depends(get_current_admin)):
    doc = await db.webhook_events.find_one({"id": eid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return serialize_doc(doc)


# -------------------- Audit --------------------
@router.get("/audit")
async def audit_list(admin=Depends(get_current_admin), limit: int = 300,
                    actor_type: Optional[str] = None, action: Optional[str] = None):
    q = {}
    if actor_type:
        q["actor_type"] = actor_type
    if action:
        q["action"] = {"$regex": action, "$options": "i"}
    docs = await db.audit_log.find(q, {"_id": 0}).sort("ts", -1).limit(limit).to_list(limit)
    return serialize_doc(docs)


# -------------------- RSA pubkey --------------------
@router.get("/rsa-public-key")
async def rsa_pubkey(admin=Depends(get_current_admin)):
    return {"pem": get_rsa_public_pem()}
