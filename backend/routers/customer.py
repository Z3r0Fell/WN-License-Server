"""Customer self-serve portal routes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from auth import (get_current_customer, hash_password, issue_session_token,
                  verify_password, _client_ip)
from audit import log as audit_log
from db import db, now_iso, serialize_doc

router = APIRouter(prefix="/customer", tags=["customer"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be 8+ chars")
    existing = await db.customers.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    
    verification_token = str(uuid.uuid4())
    doc = {
        "id": str(uuid.uuid4()),
        "email": body.email.lower(),
        "name": body.name or body.email.split("@")[0],
        "password_hash": hash_password(body.password),
        "created_at": now_iso(),
        "email_verified": False,
        "email_verification_token": verification_token,
    }
    await db.customers.insert_one(doc)
    
    try:
        from email_sender import send_email
        import runtime_settings as rs
        portal = (rs.get("CUSTOMER_PORTAL_URL")
                  or rs.get("APP_PUBLIC_URL", "https://licenses.watchnexus.ca")).rstrip("/")
        verify_url = f"{portal}/portal/verify-email?token={verification_token}"
        html = f"""
        <p>Hello {doc['name']},</p>
        <p>Thanks for registering. Please verify your email by clicking the link below:</p>
        <p><a href="{verify_url}">Verify Email</a></p>
        <p>If you didn't create this account, you can ignore this email.</p>
        """
        send_email(body.email, "Verify your email", html)
    except Exception:
        import logging
        logging.getLogger("watchnexus").exception("customer verification email failed")
    
    await audit_log("customer", doc["id"], doc["email"], "customer.register",
                    ip=_client_ip(request))
    return {"token": None, "user": {"id": doc["id"], "email": doc["email"], "name": doc["name"], "email_verified": False}}


@router.post("/verify-email")
async def verify_email(body: dict):
    token = body.get("token")
    if not token:
        raise HTTPException(400, "Missing token")
    user = await db.customers.find_one({"email_verification_token": token}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Invalid or expired verification token")
    await db.customers.update_one(
        {"id": user["id"]},
        {"$set": {"email_verified": True, "email_verification_token": None}},
    )
    return {"ok": True}


@router.post("/login")
async def login(body: LoginIn, request: Request):
    from auth import _check_lockout, _record_failed_attempt, _clear_failed_attempts, _client_ip
    ip = _client_ip(request)
    lockout = await _check_lockout("customers", body.email.lower(), ip)
    if lockout:
        raise HTTPException(403, f"Account locked. Try again in {lockout} seconds")
    user = await db.customers.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        await _record_failed_attempt("customers", body.email.lower(), ip)
        raise HTTPException(401, "Invalid credentials")
    await _clear_failed_attempts("customers", body.email.lower())
    if not user.get("email_verified"):
        raise HTTPException(403, "Email not verified. Check your inbox for the verification link.")
    token = issue_session_token(user["id"], "customer", user["email"])
    await audit_log("customer", user["id"], user["email"], "customer.login",
                    ip=ip)
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name")}}


@router.get("/me")
async def me(customer=Depends(get_current_customer)):
    return {"id": customer["id"], "email": customer["email"], "name": customer.get("name")}


@router.get("/licenses")
async def my_licenses(customer=Depends(get_current_customer)):
    docs = await db.licenses.find({"customer_email": customer["email"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for d in docs:
        d["activations_count"] = await db.activations.count_documents(
            {"license_id": d["id"], "status": "active"})
    return serialize_doc(docs)


@router.get("/licenses/{lid}")
async def license_detail(lid: str, customer=Depends(get_current_customer)):
    lic = await db.licenses.find_one({"id": lid, "customer_email": customer["email"]}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "Not found")
    activations = await db.activations.find({"license_id": lid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"license": serialize_doc(lic), "activations": serialize_doc(activations)}


@router.post("/licenses/{lid}/activations/{aid}/deactivate")
async def deactivate_install(lid: str, aid: str, customer=Depends(get_current_customer)):
    lic = await db.licenses.find_one({"id": lid, "customer_email": customer["email"]})
    if not lic:
        raise HTTPException(404, "License not found")
    res = await db.activations.update_one(
        {"id": aid, "license_id": lid, "status": "active"},
        {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                  "deactivated_reason": "customer_action"}})
    if not res.matched_count:
        raise HTTPException(404, "Activation not found")
    await audit_log("customer", customer["id"], customer["email"], "activation.deactivate",
                    "activation", aid, severity="warning", meta={"license_id": lid})
    return {"ok": True}


@router.get("/builds")
async def my_builds(customer=Depends(get_current_customer)):
    licenses = await db.licenses.find({"customer_email": customer["email"], "status": "active"}, {"_id": 0}).to_list(200)
    product_ids = list({lic["product_id"] for lic in licenses})
    if not product_ids:
        return []
    builds = await db.builds.find({"product_id": {"$in": product_ids}}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return serialize_doc(builds)
