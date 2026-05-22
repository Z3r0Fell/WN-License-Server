"""Admin routes: login, products, licenses, activations, customers, audit, api keys, builds, webhooks list, dashboard."""
import csv
import io
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, EmailStr, Field

from auth import (get_current_admin, hash_password, verify_password,
                  require_admin_role, issue_session_token)
from audit import log as audit_log
from crypto_core import (generate_hmac_license, generate_rsa_license,
                         get_rsa_public_pem)
from db import db, now_iso, serialize_doc
import jwt as _jwt
import mfa
import runtime_settings

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------- Auth --------------------
class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


# Short-lived MFA challenge token. Issued by /login when 2FA is required,
# consumed by /login/2fa to mint the real session JWT.
MFA_CHALLENGE_TTL_SECONDS = 5 * 60


def _client_ip(request: Request) -> Optional[str]:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


def _issue_mfa_challenge(user_id: str) -> str:
    now = int(time.time())
    secret = os.environ.get("JWT_SECRET", "dev-secret")
    return _jwt.encode(
        {
            "sub": user_id,
            "purpose": "mfa-challenge",
            "iat": now,
            "exp": now + MFA_CHALLENGE_TTL_SECONDS,
            "iss": "watchnexus-mfa",
        },
        secret,
        algorithm="HS256",
    )


def _decode_mfa_challenge(token: str) -> Optional[str]:
    secret = os.environ.get("JWT_SECRET", "dev-secret")
    try:
        claims = _jwt.decode(token, secret, algorithms=["HS256"],
                             issuer="watchnexus-mfa")
        if claims.get("purpose") != "mfa-challenge":
            return None
        return claims.get("sub")
    except _jwt.InvalidTokenError:
        return None


@router.post("/login")
async def admin_login(body: AdminLoginIn, request: Request):
    ip = _client_ip(request)
    # IP allowlist (admin-only restriction; webhook/customer routes unaffected).
    if not mfa.admin_login_ip_allowed(ip):
        await audit_log("admin", None, body.email.lower(), "admin.login_ip_blocked",
                        severity="warning", ip=ip,
                        meta={"reason": "ip_not_in_allowlist"})
        raise HTTPException(403, "This IP address is not allowed to sign in. "
                                  "Contact your administrator.")
    user = await db.admin_users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if user.get("is_active") is False:
        raise HTTPException(403, "Account disabled")
    # If the user has 2FA enabled, do not issue a full session yet.
    if user.get("totp_enabled"):
        challenge = _issue_mfa_challenge(user["id"])
        await audit_log("admin", user["id"], user["email"], "admin.login_mfa_required",
                        severity="info", ip=ip)
        return {
            "require_2fa": True,
            "mfa_token": challenge,
            "expires_in": MFA_CHALLENGE_TTL_SECONDS,
        }
    token = issue_session_token(user["id"], "admin", user["email"])
    await db.admin_users.update_one(
        {"id": user["id"]}, {"$set": {"last_login_at": now_iso()}}
    )
    await audit_log("admin", user["id"], user["email"], "admin.login",
                    severity="info", ip=ip)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "admin_role": user.get("admin_role") or "admin",
        },
    }


class AdminLogin2FAIn(BaseModel):
    mfa_token: str
    code: Optional[str] = None            # TOTP 6-digit
    recovery_code: Optional[str] = None   # one-time recovery code


@router.post("/login/2fa")
async def admin_login_2fa(body: AdminLogin2FAIn, request: Request):
    ip = _client_ip(request)
    if not mfa.admin_login_ip_allowed(ip):
        raise HTTPException(403, "This IP address is not allowed to sign in.")
    if not body.code and not body.recovery_code:
        raise HTTPException(400, "Provide either code or recovery_code")
    user_id = _decode_mfa_challenge(body.mfa_token)
    if not user_id:
        raise HTTPException(401, "MFA session expired - please log in again")
    user = await db.admin_users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("totp_enabled"):
        raise HTTPException(401, "MFA not enabled for this account")
    if user.get("is_active") is False:
        raise HTTPException(403, "Account disabled")

    ok = False
    consumed_recovery = False
    if body.code:
        ok = mfa.verify_totp(user.get("totp_secret") or "", body.code)
    if not ok and body.recovery_code:
        new_codes = mfa.consume_recovery_code(
            user.get("totp_recovery_hashes") or [], body.recovery_code
        )
        if new_codes is not None:
            ok = True
            consumed_recovery = True
            await db.admin_users.update_one(
                {"id": user["id"]},
                {"$set": {"totp_recovery_hashes": new_codes}},
            )
    if not ok:
        await audit_log("admin", user["id"], user["email"], "admin.login_2fa_failed",
                        severity="warning", ip=ip)
        raise HTTPException(401, "Invalid code")

    token = issue_session_token(user["id"], "admin", user["email"])
    await db.admin_users.update_one(
        {"id": user["id"]}, {"$set": {"last_login_at": now_iso()}}
    )
    await audit_log("admin", user["id"], user["email"],
                    "admin.login_2fa" + ("_recovery" if consumed_recovery else ""),
                    severity="info", ip=ip)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "admin_role": user.get("admin_role") or "admin",
        },
        "used_recovery_code": consumed_recovery,
        "recovery_codes_remaining": len(user.get("totp_recovery_hashes") or [])
                                    - (1 if consumed_recovery else 0),
    }


@router.get("/me")
async def admin_me(admin=Depends(get_current_admin)):
    return {
        "id": admin["id"],
        "email": admin["email"],
        "name": admin.get("name"),
        "admin_role": admin.get("admin_role") or "admin",
        "is_active": admin.get("is_active", True),
        "totp_enabled": bool(admin.get("totp_enabled")),
        "recovery_codes_remaining": len(admin.get("totp_recovery_hashes") or []),
    }


# -------------------- 2FA enrollment --------------------
class Verify2FAIn(BaseModel):
    secret: str        # base32 secret returned by /enroll
    code: str          # 6-digit TOTP entered by user
    current_password: str  # extra confirmation before enabling


class Disable2FAIn(BaseModel):
    current_password: str
    code: Optional[str] = None            # accept TOTP or recovery code
    recovery_code: Optional[str] = None


@router.post("/me/2fa/enroll")
async def me_2fa_enroll(admin=Depends(get_current_admin)):
    """Generate a fresh secret + QR code. Caller must POST to /verify to enable."""
    secret = mfa.new_secret()
    uri = mfa.provisioning_uri(secret, admin["email"])
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_png_data_uri": mfa.qr_png_data_uri(uri),
    }


@router.post("/me/2fa/verify")
async def me_2fa_verify(body: Verify2FAIn, request: Request,
                         admin=Depends(get_current_admin)):
    """Confirm a TOTP code against the secret. On success, enable 2FA and
    return one-time recovery codes (shown ONCE)."""
    fresh = await db.admin_users.find_one({"id": admin["id"]}, {"_id": 0})
    if not verify_password(body.current_password, fresh["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if not mfa.verify_totp(body.secret, body.code):
        raise HTTPException(400, "Invalid code. Make sure your device clock is in sync.")
    recovery = mfa.new_recovery_codes()
    await db.admin_users.update_one(
        {"id": admin["id"]},
        {"$set": {
            "totp_secret": body.secret,
            "totp_enabled": True,
            "totp_enabled_at": now_iso(),
            "totp_recovery_hashes": mfa.hash_recovery_codes(recovery),
        }},
    )
    await audit_log("admin", admin["id"], admin["email"], "admin_user.2fa_enabled",
                    "admin_user", admin["id"], severity="warning",
                    ip=request.client.host if request.client else None)
    return {"ok": True, "recovery_codes": recovery}


@router.post("/me/2fa/disable")
async def me_2fa_disable(body: Disable2FAIn, request: Request,
                          admin=Depends(get_current_admin)):
    fresh = await db.admin_users.find_one({"id": admin["id"]}, {"_id": 0})
    if not verify_password(body.current_password, fresh["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if not fresh.get("totp_enabled"):
        return {"ok": True, "already_disabled": True}
    ok = False
    if body.code:
        ok = mfa.verify_totp(fresh.get("totp_secret") or "", body.code)
    if not ok and body.recovery_code:
        ok = mfa.consume_recovery_code(
            fresh.get("totp_recovery_hashes") or [], body.recovery_code
        ) is not None
    if not ok:
        raise HTTPException(400, "Invalid 2FA code")
    await db.admin_users.update_one(
        {"id": admin["id"]},
        {"$set": {"totp_enabled": False},
         "$unset": {"totp_secret": "", "totp_recovery_hashes": "",
                    "totp_enabled_at": ""}},
    )
    await audit_log("admin", admin["id"], admin["email"], "admin_user.2fa_disabled",
                    "admin_user", admin["id"], severity="warning",
                    ip=request.client.host if request.client else None)
    return {"ok": True}


@router.post("/me/2fa/regenerate-recovery")
async def me_2fa_regenerate(body: Disable2FAIn, request: Request,
                             admin=Depends(get_current_admin)):
    """Replace recovery codes (requires current password + a current TOTP code)."""
    fresh = await db.admin_users.find_one({"id": admin["id"]}, {"_id": 0})
    if not verify_password(body.current_password, fresh["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if not fresh.get("totp_enabled"):
        raise HTTPException(400, "2FA is not enabled")
    if not body.code or not mfa.verify_totp(fresh.get("totp_secret") or "", body.code):
        raise HTTPException(400, "Invalid TOTP code")
    recovery = mfa.new_recovery_codes()
    await db.admin_users.update_one(
        {"id": admin["id"]},
        {"$set": {"totp_recovery_hashes": mfa.hash_recovery_codes(recovery)}},
    )
    await audit_log("admin", admin["id"], admin["email"],
                    "admin_user.2fa_recovery_regenerated", "admin_user", admin["id"],
                    severity="warning",
                    ip=request.client.host if request.client else None)
    return {"ok": True, "recovery_codes": recovery}


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
async def products_create(body: ProductIn, request: Request, admin=Depends(require_admin_role("admin"))):
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
async def products_update(pid: str, body: ProductIn, admin=Depends(require_admin_role("admin"))):
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
async def products_delete(pid: str, admin=Depends(require_admin_role("admin"))):
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
    # Send purchase email if a customer email is set
    if customer_email:
        try:
            from email_sender import render_purchase_email, send_email
            import runtime_settings as rs
            portal_url = (rs.get("CUSTOMER_PORTAL_URL")
                          or rs.get("APP_PUBLIC_URL").rstrip("/") + "/portal")
            subject, html = render_purchase_email(
                customer_email=customer_email,
                license_key=key,
                product_name=product.get("name") or product["slug"],
                plan=plan,
                seats=seats,
                source=source,
                portal_url=portal_url,
            )
            send_email(customer_email, subject, html)
        except Exception:
            import logging
            logging.getLogger("watchnexus").exception("admin license email failed")
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
async def licenses_create(body: LicenseIn, request: Request, admin=Depends(require_admin_role("admin"))):
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
async def license_update(lid: str, body: LicenseUpdate, admin=Depends(require_admin_role("admin"))):
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
async def license_revoke(lid: str, admin=Depends(require_admin_role("admin"))):
    res = await db.licenses.update_one({"id": lid}, {"$set": {"status": "revoked", "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await db.activations.update_many({"license_id": lid, "status": "active"},
                                     {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                                               "deactivated_reason": "license_revoked"}})
    await audit_log("admin", admin["id"], admin["email"], "license.revoke", "license", lid, severity="warning")
    return {"ok": True}


@router.post("/licenses/{lid}/extend")
async def license_extend(lid: str, body: dict, admin=Depends(require_admin_role("admin"))):
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
                                admin=Depends(require_admin_role("admin"))):
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
    allowed_ips: list[str] = Field(default_factory=list)


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    allowed_ips: Optional[list[str]] = None


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
async def api_keys_create(body: ApiKeyIn, admin=Depends(require_admin_role("admin"))):
    raw = "wnk_" + secrets.token_urlsafe(32)
    doc = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "product_id": body.product_id,
        "scopes": body.scopes,
        "allowed_ips": body.allowed_ips or [],
        "key": raw,
        "status": "active",
        "created_at": now_iso(),
        "last_used_at": None,
        "last_used_ip": None,
    }
    await db.api_keys.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "api_key.create",
                    "api_key", doc["id"], severity="warning")
    return {"id": doc["id"], "name": doc["name"], "key": raw, "created_at": doc["created_at"],
            "product_id": doc["product_id"], "scopes": doc["scopes"], "status": doc["status"],
            "allowed_ips": doc["allowed_ips"]}


@router.patch("/api-keys/{kid}")
async def api_keys_update(kid: str, body: ApiKeyUpdate, admin=Depends(require_admin_role("admin"))):
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields to update")
    res = await db.api_keys.find_one_and_update(
        {"id": kid}, {"$set": payload}, return_document=True,
        projection={"_id": 0, "key": 0},
    )
    if not res:
        raise HTTPException(404, "Not found")
    await audit_log("admin", admin["id"], admin["email"], "api_key.update",
                    "api_key", kid, meta=payload)
    return serialize_doc(res)


@router.post("/api-keys/{kid}/revoke")
async def api_keys_revoke(kid: str, admin=Depends(require_admin_role("admin"))):
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
async def builds_create(body: BuildIn, admin=Depends(require_admin_role("admin"))):
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
async def builds_delete(bid: str, admin=Depends(require_admin_role("admin"))):
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
                    actor_type: Optional[str] = None, action: Optional[str] = None,
                    actor_id: Optional[str] = None, actor_email: Optional[str] = None,
                    severity: Optional[str] = None,
                    since: Optional[str] = None, until: Optional[str] = None):
    q: dict = {}
    if actor_type:
        q["actor_type"] = actor_type
    if action:
        q["action"] = {"$regex": action, "$options": "i"}
    if actor_id:
        q["actor_id"] = actor_id
    if actor_email:
        q["actor_email"] = {"$regex": actor_email, "$options": "i"}
    if severity:
        q["severity"] = severity
    if since or until:
        ts_q: dict = {}
        if since:
            ts_q["$gte"] = since
        if until:
            ts_q["$lte"] = until
        q["ts"] = ts_q
    limit = max(1, min(int(limit or 300), 1000))
    docs = await db.audit_log.find(q, {"_id": 0}).sort("ts", -1).limit(limit).to_list(limit)
    return serialize_doc(docs)


@router.get("/audit/actors")
async def audit_actors(admin=Depends(get_current_admin)):
    """Return a small directory of distinct actors that appear in the audit log
    (used to populate the filter dropdown in the UI)."""
    pipeline = [
        {"$match": {"actor_type": {"$in": ["admin", "customer", "integrator", "webhook"]}}},
        {"$group": {"_id": {"id": "$actor_id", "email": "$actor_email",
                            "type": "$actor_type"},
                    "events": {"$sum": 1},
                    "last_seen": {"$max": "$ts"}}},
        {"$sort": {"last_seen": -1}},
        {"$limit": 200},
    ]
    rows = await db.audit_log.aggregate(pipeline).to_list(200)
    out = []
    for r in rows:
        k = r["_id"]
        if not k.get("id") and not k.get("email"):
            continue
        out.append({
            "actor_id": k.get("id"),
            "actor_email": k.get("email"),
            "actor_type": k.get("type"),
            "events": r.get("events", 0),
            "last_seen": r.get("last_seen"),
        })
    return out


# -------------------- RSA pubkey --------------------
@router.get("/rsa-public-key")
async def rsa_pubkey(admin=Depends(get_current_admin)):
    return {"pem": get_rsa_public_pem()}


# -------------------- Runtime settings --------------------
@router.get("/settings")
async def settings_list(admin=Depends(get_current_admin)):
    """Return all editable settings (secrets returned masked + has_value flag)."""
    return runtime_settings.public_view()


class SettingsUpdate(BaseModel):
    values: dict[str, str | None]


@router.put("/settings")
async def settings_update(body: SettingsUpdate, request: Request,
                          admin=Depends(require_admin_role("admin"))):
    """Bulk upsert. Unknown keys ignored. Pass empty string to clear a value.
    Returns the refreshed public view."""
    accepted = {k: (v or "") for k, v in body.values.items()
                if k in runtime_settings.EDITABLE_KEYS}
    await runtime_settings.set_many(accepted, actor_email=admin.get("email"))
    await audit_log("admin", admin["id"], admin["email"], "settings.update",
                    severity="warning",
                    meta={"keys": sorted(list(accepted.keys()))},
                    ip=request.client.host if request.client else None)
    return runtime_settings.public_view()


@router.post("/settings/test-email")
async def settings_test_email(body: dict, admin=Depends(require_admin_role("admin"))):
    """Send a test email to verify SendGrid/SMTP configuration."""
    to = (body.get("to") or admin.get("email") or "").strip()
    if not to:
        raise HTTPException(400, "Missing 'to' address")
    from email_sender import send_email
    result = send_email(
        to=to,
        subject="WatchNexus test email",
        html=(
            "<p>Hello from your <b>WatchNexus Licensing Server</b>.</p>"
            "<p>If you're reading this, the email provider is configured correctly.</p>"
            "<p style='color:#64748B;font-size:12px'>Sent from the /admin/settings test button.</p>"
        ),
    )
    await audit_log("admin", admin["id"], admin["email"], "settings.test_email",
                    meta={"to": to, "provider": result.get("provider"),
                          "sent": result.get("sent", False)})
    return result
