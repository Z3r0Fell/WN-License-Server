"""Server-to-server integrator endpoints (used by your product/app).
Protected by X-API-Key. Rate limited."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import get_api_key
from audit import log as audit_log
from crypto_core import (compute_fingerprint, get_rsa_public_pem,
                         issue_activation_token, validate_activation_token,
                         verify_hmac_license, verify_rsa_license)
from db import db, now_iso, serialize_doc

import os

router = APIRouter(prefix="/integrate", tags=["integrate"])


class ActivateIn(BaseModel):
    license_key: str
    hardware_id: Optional[str] = None
    domain: Optional[str] = None
    device_name: Optional[str] = Field(None, max_length=120)


class ValidateIn(BaseModel):
    activation_token: str
    hardware_id: Optional[str] = None
    domain: Optional[str] = None


class DeactivateIn(BaseModel):
    activation_token: Optional[str] = None
    license_key: Optional[str] = None
    hardware_id: Optional[str] = None
    domain: Optional[str] = None


async def _resolve_license(key: str) -> dict | None:
    """Verify a license key signature and load the DB record."""
    lic = await db.licenses.find_one({"key": key}, {"_id": 0})
    if not lic:
        return None
    if lic["signing_method"] == "rsa":
        ok = verify_rsa_license(key)
    else:
        ok = verify_hmac_license(key, os.environ.get("HMAC_LICENSE_SECRET", "dev").encode())
    return lic if ok else None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/activate")
async def activate(body: ActivateIn, request: Request, api_key=Depends(get_api_key)):
    lic = await _resolve_license(body.license_key)
    if not lic:
        raise HTTPException(400, "Invalid license key")
    if lic["status"] != "active":
        raise HTTPException(403, f"License is {lic['status']}")
    if lic.get("expires_at"):
        # if expires_at < now then expire it
        from datetime import datetime, timezone
        try:
            exp_dt = datetime.fromisoformat(lic["expires_at"].replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                await db.licenses.update_one({"id": lic["id"]}, {"$set": {"status": "expired"}})
                raise HTTPException(403, "License is expired")
        except ValueError:
            pass

    fp = compute_fingerprint(lic["fingerprint_mode"], body.hardware_id, body.domain)

    # Existing activation? Same fingerprint => reuse.
    existing = await db.activations.find_one(
        {"license_id": lic["id"], "fingerprint": fp, "status": "active"}, {"_id": 0})
    if existing:
        token = issue_activation_token(lic["id"], fp, existing["id"])
        await db.activations.update_one(
            {"id": existing["id"]},
            {"$set": {"last_seen_at": now_iso(), "last_ip": _client_ip(request)}})
        return {
            "activation_id": existing["id"],
            "activation_token": token["token"],
            "expires_at": token["exp"],
            "grace_until": token["grace_until"],
            "license": {"id": lic["id"], "plan": lic["plan"], "product": lic["product_slug"]},
            "reused": True,
        }

    # Seat check
    active_count = await db.activations.count_documents(
        {"license_id": lic["id"], "status": "active"})
    if active_count >= lic["seats"]:
        raise HTTPException(403, f"Seat limit reached ({lic['seats']}). Deactivate a device first.")

    # Create new
    aid = str(uuid.uuid4())
    doc = {
        "id": aid,
        "license_id": lic["id"],
        "product_slug": lic["product_slug"],
        "customer_email": lic.get("customer_email"),
        "fingerprint": fp,
        "hardware_id": body.hardware_id,
        "domain": body.domain,
        "device_name": body.device_name or (body.hardware_id or body.domain or "unknown device"),
        "status": "active",
        "created_at": now_iso(),
        "last_seen_at": now_iso(),
        "first_ip": _client_ip(request),
        "last_ip": _client_ip(request),
    }
    await db.activations.insert_one(doc)
    token = issue_activation_token(lic["id"], fp, aid)
    await audit_log("integrator", api_key.get("id"), api_key.get("name"),
                    "activation.create", "activation", aid,
                    meta={"license_id": lic["id"], "fp": fp[:12]},
                    ip=_client_ip(request))
    return {
        "activation_id": aid,
        "activation_token": token["token"],
        "expires_at": token["exp"],
        "grace_until": token["grace_until"],
        "license": {"id": lic["id"], "plan": lic["plan"], "product": lic["product_slug"]},
        "reused": False,
    }


@router.post("/validate")
async def validate(body: ValidateIn, request: Request, api_key=Depends(get_api_key)):
    decoded = validate_activation_token(body.activation_token)
    if not decoded["valid"]:
        return {"valid": False, "mode": decoded["mode"], "reason": decoded.get("reason")}
    claims = decoded["claims"]
    lic = await db.licenses.find_one({"id": claims["sub"]}, {"_id": 0})
    if not lic:
        return {"valid": False, "mode": "license_not_found"}
    if lic["status"] != "active":
        return {"valid": False, "mode": f"license_{lic['status']}"}
    activation = await db.activations.find_one({"id": claims.get("aid")}, {"_id": 0})
    if not activation or activation["status"] != "active":
        return {"valid": False, "mode": "activation_revoked"}
    # Re-compute fingerprint if client provided ids
    if body.hardware_id or body.domain:
        new_fp = compute_fingerprint(lic["fingerprint_mode"], body.hardware_id, body.domain)
        if new_fp != claims.get("fp"):
            return {"valid": False, "mode": "fingerprint_mismatch"}
    await db.activations.update_one({"id": activation["id"]},
                                    {"$set": {"last_seen_at": now_iso(),
                                              "last_ip": _client_ip(request)}})
    return {
        "valid": True,
        "mode": decoded["mode"],
        "license": {"id": lic["id"], "plan": lic["plan"], "product": lic["product_slug"],
                    "expires_at": lic.get("expires_at"), "seats": lic["seats"]},
        "activation": {"id": activation["id"], "device_name": activation.get("device_name")},
        "expires_at": claims.get("exp"),
        "grace_until": claims.get("grace_until"),
    }


@router.post("/deactivate")
async def deactivate(body: DeactivateIn, request: Request, api_key=Depends(get_api_key)):
    activation_id = None
    if body.activation_token:
        d = validate_activation_token(body.activation_token)
        if d["valid"]:
            activation_id = d["claims"].get("aid")
    if not activation_id and body.license_key:
        lic = await _resolve_license(body.license_key)
        if not lic:
            raise HTTPException(400, "Invalid license key")
        fp = compute_fingerprint(lic["fingerprint_mode"], body.hardware_id, body.domain)
        existing = await db.activations.find_one(
            {"license_id": lic["id"], "fingerprint": fp, "status": "active"})
        if existing:
            activation_id = existing["id"]
    if not activation_id:
        raise HTTPException(404, "Activation not found")
    res = await db.activations.update_one(
        {"id": activation_id, "status": "active"},
        {"$set": {"status": "deactivated", "deactivated_at": now_iso(),
                  "deactivated_reason": "client_request"}})
    if not res.matched_count:
        raise HTTPException(404, "Already deactivated")
    await audit_log("integrator", api_key.get("id"), api_key.get("name"),
                    "activation.deactivate", "activation", activation_id, severity="warning",
                    ip=_client_ip(request))
    return {"ok": True, "activation_id": activation_id}


@router.get("/rsa-public-key")
async def public_key():
    """Public RSA key for offline license verification by clients."""
    return {"pem": get_rsa_public_pem()}
