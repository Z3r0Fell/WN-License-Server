"""Admin user management: list / create / update / delete / change-password /
reset-password / invite / accept-invite.

Roles:
    - "admin"   : full access (default for the seeded user)
    - "support" : read-only across the app + can deactivate individual seats.
                  Cannot modify settings, products, licenses (create/revoke),
                  api-keys, builds, or other admins.
"""
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth import (get_current_admin, hash_password, verify_password,
                  require_admin_role, issue_session_token)
from audit import log as audit_log
from db import db, now_iso, serialize_doc
import runtime_settings as rs

router = APIRouter(prefix="/admin", tags=["admin-users"])


# ---------------------------------------------------------------------------
# Self-service
# ---------------------------------------------------------------------------
class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/me/change-password")
async def change_my_password(body: ChangePasswordIn, request: Request,
                              admin=Depends(get_current_admin)):
    """Any logged-in admin can rotate their own password."""
    user = await db.admin_users.find_one({"id": admin["id"]}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Admin not found")
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    await db.admin_users.update_one(
        {"id": admin["id"]},
        {"$set": {"password_hash": hash_password(body.new_password),
                  "password_changed_at": now_iso()}},
    )
    await audit_log("admin", admin["id"], admin["email"], "admin_user.change_own_password",
                    "admin_user", admin["id"], severity="warning",
                    ip=request.client.host if request.client else None)
    return {"ok": True}


# ---------------------------------------------------------------------------
# User management (admin-role only)
# ---------------------------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_SUPPORT = "support"
VALID_ROLES = {ROLE_ADMIN, ROLE_SUPPORT}


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name"),
        "admin_role": u.get("admin_role") or ROLE_ADMIN,
        "is_active": u.get("is_active", True),
        "created_at": u.get("created_at"),
        "last_login_at": u.get("last_login_at"),
        "password_changed_at": u.get("password_changed_at"),
    }


@router.get("/users")
async def list_users(admin=Depends(require_admin_role(ROLE_ADMIN, ROLE_SUPPORT))):
    """All admins can SEE the user list. Only admins can mutate it."""
    docs = await db.admin_users.find({}, {"_id": 0, "password_hash": 0}) \
        .sort("created_at", 1).to_list(500)
    return [_public_user(d) for d in docs]


class CreateUserIn(BaseModel):
    email: EmailStr
    name: str
    admin_role: str = Field(ROLE_ADMIN, pattern=f"^({ROLE_ADMIN}|{ROLE_SUPPORT})$")
    password: str = Field(min_length=8, max_length=200)
    is_active: bool = True


@router.post("/users")
async def create_user(body: CreateUserIn, request: Request,
                       admin=Depends(require_admin_role(ROLE_ADMIN))):
    email = body.email.lower()
    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(400, "An admin with that email already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": body.name,
        "admin_role": body.admin_role,
        "is_active": body.is_active,
        "password_hash": hash_password(body.password),
        "created_at": now_iso(),
        "created_by": admin["email"],
        "last_login_at": None,
    }
    await db.admin_users.insert_one(doc)
    await audit_log("admin", admin["id"], admin["email"], "admin_user.create",
                    "admin_user", doc["id"], severity="warning",
                    meta={"email": email, "role": body.admin_role},
                    ip=request.client.host if request.client else None)
    return _public_user(doc)


class UpdateUserIn(BaseModel):
    name: Optional[str] = None
    admin_role: Optional[str] = Field(default=None, pattern=f"^({ROLE_ADMIN}|{ROLE_SUPPORT})$")
    is_active: Optional[bool] = None


@router.patch("/users/{uid}")
async def update_user(uid: str, body: UpdateUserIn, request: Request,
                       admin=Depends(require_admin_role(ROLE_ADMIN))):
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields to update")
    target = await db.admin_users.find_one({"id": uid}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")

    # Guards: don't lock yourself out, and don't demote/disable the last admin.
    if target["id"] == admin["id"]:
        if "admin_role" in payload and payload["admin_role"] != ROLE_ADMIN:
            raise HTTPException(400, "You cannot demote your own role")
        if payload.get("is_active") is False:
            raise HTTPException(400, "You cannot disable your own account")

    if (payload.get("admin_role") == ROLE_SUPPORT or payload.get("is_active") is False) \
            and target.get("admin_role") == ROLE_ADMIN:
        # Make sure at least one OTHER active admin would remain.
        other_admins = await db.admin_users.count_documents({
            "id": {"$ne": uid},
            "admin_role": ROLE_ADMIN,
            "is_active": {"$ne": False},
        })
        if other_admins == 0:
            raise HTTPException(400, "Cannot demote or disable the last remaining admin")

    payload["updated_at"] = now_iso()
    await db.admin_users.update_one({"id": uid}, {"$set": payload})
    fresh = await db.admin_users.find_one({"id": uid}, {"_id": 0})
    await audit_log("admin", admin["id"], admin["email"], "admin_user.update",
                    "admin_user", uid, severity="warning", meta=payload,
                    ip=request.client.host if request.client else None)
    return _public_user(fresh)


@router.delete("/users/{uid}")
async def delete_user(uid: str, request: Request,
                       admin=Depends(require_admin_role(ROLE_ADMIN))):
    target = await db.admin_users.find_one({"id": uid}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target["id"] == admin["id"]:
        raise HTTPException(400, "You cannot delete your own account")
    if target.get("admin_role") == ROLE_ADMIN:
        other_admins = await db.admin_users.count_documents({
            "id": {"$ne": uid},
            "admin_role": ROLE_ADMIN,
            "is_active": {"$ne": False},
        })
        if other_admins == 0:
            raise HTTPException(400, "Cannot delete the last remaining admin")
    await db.admin_users.delete_one({"id": uid})
    await audit_log("admin", admin["id"], admin["email"], "admin_user.delete",
                    "admin_user", uid, severity="warning",
                    meta={"email": target.get("email")},
                    ip=request.client.host if request.client else None)
    return {"ok": True}


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/users/{uid}/reset-password")
async def reset_password(uid: str, body: ResetPasswordIn, request: Request,
                          admin=Depends(require_admin_role(ROLE_ADMIN))):
    """An admin sets another user's password directly."""
    target = await db.admin_users.find_one({"id": uid}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    await db.admin_users.update_one(
        {"id": uid},
        {"$set": {"password_hash": hash_password(body.new_password),
                  "password_changed_at": now_iso()}},
    )
    await audit_log("admin", admin["id"], admin["email"], "admin_user.reset_password",
                    "admin_user", uid, severity="warning",
                    meta={"email": target.get("email")},
                    ip=request.client.host if request.client else None)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Email invite flow
# ---------------------------------------------------------------------------
INVITE_TTL_HOURS = 72


class InviteUserIn(BaseModel):
    email: EmailStr
    name: str
    admin_role: str = Field(ROLE_ADMIN, pattern=f"^({ROLE_ADMIN}|{ROLE_SUPPORT})$")


def _build_invite_url(token: str) -> str:
    base = (rs.get("APP_PUBLIC_URL") or os.environ.get("APP_PUBLIC_URL") or "").rstrip("/")
    if not base:
        base = ""  # caller can prepend their own
    return f"{base}/admin/accept-invite?token={token}"


@router.post("/users/invite")
async def invite_user(body: InviteUserIn, request: Request,
                       admin=Depends(require_admin_role(ROLE_ADMIN))):
    """Create an invite token and email a sign-up link. Requires SendGrid/SMTP configured."""
    email = body.email.lower()
    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(400, "An admin with that email already exists")

    token = secrets.token_urlsafe(40)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)).isoformat()

    invite_doc = {
        "id": str(uuid.uuid4()),
        "token": token,
        "email": email,
        "name": body.name,
        "admin_role": body.admin_role,
        "created_at": now_iso(),
        "created_by": admin["email"],
        "expires_at": expires_at,
        "status": "pending",
    }
    await db.admin_invites.insert_one(invite_doc)

    invite_url = _build_invite_url(token)

    # Send the invite email (best-effort - if email is unconfigured, surface the URL).
    sent = {"sent": False, "provider": None}
    try:
        from email_sender import send_email
        brand = rs.get("EMAIL_FROM_BRAND") or "WatchNexus"
        subject = f"You've been invited to the {brand} admin"
        html = (
            f"<p>Hello {body.name or email},</p>"
            f"<p>{admin.get('email')} invited you to the <b>{brand}</b> licensing admin "
            f"as a <b>{body.admin_role}</b>.</p>"
            f"<p>Click the link below to set your password and sign in. The link "
            f"expires in {INVITE_TTL_HOURS} hours.</p>"
            f"<p><a href=\"{invite_url}\" style=\"display:inline-block;padding:10px 16px;"
            f"background:#0ea5e9;color:#fff;text-decoration:none;border-radius:8px\">"
            f"Accept invite</a></p>"
            f"<p style=\"color:#64748B;font-size:12px;word-break:break-all\">"
            f"Or copy this URL: {invite_url}</p>"
        )
        sent = send_email(email, subject, html)
    except Exception as e:
        import logging
        logging.getLogger("watchnexus").warning("invite email failed: %s", e)

    await audit_log("admin", admin["id"], admin["email"], "admin_user.invite",
                    "admin_user", invite_doc["id"], severity="warning",
                    meta={"email": email, "role": body.admin_role,
                          "email_sent": sent.get("sent", False)},
                    ip=request.client.host if request.client else None)

    # Always return the URL so the inviter can hand it over manually if email failed.
    return {
        "ok": True,
        "invite_id": invite_doc["id"],
        "email": email,
        "expires_at": expires_at,
        "invite_url": invite_url,
        "email_sent": sent.get("sent", False),
        "email_provider": sent.get("provider"),
    }


@router.get("/users/invites")
async def list_invites(admin=Depends(require_admin_role(ROLE_ADMIN))):
    docs = await db.admin_invites.find({}, {"_id": 0, "token": 0}) \
        .sort("created_at", -1).to_list(200)
    return serialize_doc(docs)


@router.delete("/users/invites/{iid}")
async def revoke_invite(iid: str, admin=Depends(require_admin_role(ROLE_ADMIN))):
    await db.admin_invites.update_one(
        {"id": iid, "status": "pending"},
        {"$set": {"status": "revoked", "revoked_at": now_iso()}},
    )
    await audit_log("admin", admin["id"], admin["email"], "admin_user.invite_revoke",
                    "admin_user", iid, severity="warning")
    return {"ok": True}


# ---------------------------------------------------------------------------
# PUBLIC: Accept invite (no auth, just the one-time token)
# ---------------------------------------------------------------------------
public_router = APIRouter(prefix="/public", tags=["admin-users-public"])


class InvitePreviewOut(BaseModel):
    email: str
    name: Optional[str] = None
    admin_role: str
    expires_at: str


@public_router.get("/invites/{token}", response_model=InvitePreviewOut)
async def preview_invite(token: str):
    doc = await db.admin_invites.find_one({"token": token, "status": "pending"}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Invite not found or already used")
    # Expiry check
    try:
        exp = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(410, "Invite has expired")
    except ValueError:
        pass
    return InvitePreviewOut(
        email=doc["email"],
        name=doc.get("name"),
        admin_role=doc.get("admin_role", ROLE_ADMIN),
        expires_at=doc["expires_at"],
    )


class AcceptInviteIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=200)


@public_router.post("/invites/accept")
async def accept_invite(body: AcceptInviteIn, request: Request):
    doc = await db.admin_invites.find_one({"token": body.token, "status": "pending"}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Invite not found or already used")
    try:
        exp = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp:
            await db.admin_invites.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "expired"}},
            )
            raise HTTPException(410, "Invite has expired")
    except ValueError:
        pass

    if await db.admin_users.find_one({"email": doc["email"]}):
        raise HTTPException(400, "Account already exists for this email")

    user = {
        "id": str(uuid.uuid4()),
        "email": doc["email"],
        "name": doc.get("name"),
        "admin_role": doc.get("admin_role", ROLE_ADMIN),
        "is_active": True,
        "password_hash": hash_password(body.password),
        "created_at": now_iso(),
        "created_by": doc.get("created_by"),
        "last_login_at": None,
    }
    await db.admin_users.insert_one(user)
    await db.admin_invites.update_one(
        {"id": doc["id"]},
        {"$set": {"status": "accepted", "accepted_at": now_iso(), "user_id": user["id"]}},
    )

    token = issue_session_token(user["id"], "admin", user["email"])
    await db.admin_users.update_one(
        {"id": user["id"]}, {"$set": {"last_login_at": now_iso()}}
    )
    await audit_log("admin", user["id"], user["email"], "admin_user.invite_accept",
                    "admin_user", user["id"], severity="warning",
                    ip=request.client.host if request.client else None)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "admin_role": user["admin_role"],
        },
    }
