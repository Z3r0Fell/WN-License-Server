"""Runtime settings: MongoDB-backed key/value store with env fallback.

Lets admins edit secrets (webhook signing keys, email creds, branding URLs)
from the /admin/settings UI without editing .env or restarting the server.

Read precedence:  DB value (if non-empty)  ->  os.environ  ->  default

Values are cached in-process for fast sync access. The cache is refreshed
on startup and after every write.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from db import db, now_iso

logger = logging.getLogger("watchnexus.settings")

# Settings keys the UI exposes. Anything not listed here is rejected on PUT.
EDITABLE_KEYS: dict[str, dict] = {
    # ---- Webhooks ----
    "STRIPE_WEBHOOK_SECRET":       {"category": "webhooks", "secret": True,
                                     "label": "Stripe webhook secret",
                                     "help": "From Stripe Dashboard \u2192 Developers \u2192 Webhooks. Starts with whsec_"},
    "LEMONSQUEEZY_WEBHOOK_SECRET": {"category": "webhooks", "secret": True,
                                     "label": "Lemon Squeezy signing secret",
                                     "help": "From Lemon Squeezy Settings \u2192 Webhooks. Plain string."},
    "PADDLE_WEBHOOK_SECRET":       {"category": "webhooks", "secret": True,
                                     "label": "Paddle webhook secret",
                                     "help": "From Paddle Notifications. The 'secret key' for the endpoint."},
    "GUMROAD_WEBHOOK_SECRET":      {"category": "webhooks", "secret": True,
                                     "label": "Gumroad webhook secret",
                                     "help": "Set per resource subscription on Gumroad."},
    # ---- Email ----
    "EMAIL_FROM":                  {"category": "email", "secret": False,
                                     "label": "From address",
                                     "help": "e.g. licenses@watchnexus.ca"},
    "EMAIL_FROM_NAME":             {"category": "email", "secret": False,
                                     "label": "From name",
                                     "help": "Display name in the email From header."},
    "SENDGRID_API_KEY":            {"category": "email", "secret": True,
                                     "label": "SendGrid API key",
                                     "help": "Starts with SG. Leave blank if using SMTP instead."},
    "SMTP_HOST":                   {"category": "email", "secret": False,
                                     "label": "SMTP host",
                                     "help": "e.g. smtp.postmarkapp.com"},
    "SMTP_PORT":                   {"category": "email", "secret": False,
                                     "label": "SMTP port",
                                     "help": "587 (STARTTLS) or 465 (SSL)"},
    "SMTP_USERNAME":               {"category": "email", "secret": False,
                                     "label": "SMTP username", "help": ""},
    "SMTP_PASSWORD":               {"category": "email", "secret": True,
                                     "label": "SMTP password", "help": ""},
    "SMTP_USE_TLS":                {"category": "email", "secret": False,
                                     "label": "Use STARTTLS",
                                     "help": "true / false. Ignored when port is 465 (always SSL)."},
    # ---- Branding / URLs ----
    "APP_PUBLIC_URL":              {"category": "branding", "secret": False,
                                     "label": "Admin / API public URL",
                                     "help": "e.g. https://licenses.watchnexus.ca"},
    "CUSTOMER_PORTAL_URL":         {"category": "branding", "secret": False,
                                     "label": "Customer portal URL",
                                     "help": "e.g. https://techhub.watchnexus.ca - used in emails and Open portal links"},
    "EMAIL_FROM_BRAND":            {"category": "branding", "secret": False,
                                     "label": "Brand name (used in emails)",
                                     "help": "Defaults to EMAIL_FROM_NAME if blank."},
}

_cache: dict[str, str] = {}
_lock = asyncio.Lock()


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def get(key: str, default: str = "") -> str:
    """Sync getter. Reads from cache, then env, then default. Non-empty wins."""
    cached = _cache.get(key)
    if cached not in (None, ""):
        return cached
    envv = _norm(os.environ.get(key))
    if envv:
        return envv
    return default


def get_bool(key: str, default: bool = False) -> bool:
    v = get(key, "").lower()
    if v in ("1", "true", "yes", "on"):  # explicit set
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get(key, str(default)))
    except (TypeError, ValueError):
        return default


async def refresh_cache() -> None:
    """Reload all editable settings from MongoDB into the cache."""
    async with _lock:
        _cache.clear()
        async for doc in db.settings.find({}, {"_id": 0}):
            key = doc.get("key")
            if key in EDITABLE_KEYS:
                _cache[key] = _norm(doc.get("value"))
        logger.info(f"runtime_settings cache loaded: {len(_cache)} key(s)")


async def set_many(updates: dict[str, str], actor_email: str | None = None) -> None:
    """Upsert multiple settings atomically (per-key writes). Unknown keys ignored."""
    ts = now_iso()
    for key, raw in updates.items():
        if key not in EDITABLE_KEYS:
            continue
        value = _norm(raw)
        await db.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": ts,
                      "updated_by": actor_email}},
            upsert=True,
        )
    await refresh_cache()


def public_view() -> dict[str, dict]:
    """Return all editable settings shaped for the admin UI.
    Secrets are returned as `{ has_value: bool, masked: 'wnk_\u2026abcd' or '' }`
    so the raw value never leaves the server."""
    out = {}
    for key, meta in EDITABLE_KEYS.items():
        raw = _cache.get(key) or _norm(os.environ.get(key))
        if meta.get("secret"):
            display = ""
            if raw:
                if len(raw) > 12:
                    display = raw[:4] + "\u2026" + raw[-4:]
                else:
                    display = "\u2022" * len(raw)
            out[key] = {
                "category": meta["category"],
                "label": meta["label"],
                "help": meta["help"],
                "secret": True,
                "has_value": bool(raw),
                "source": "db" if _cache.get(key) else ("env" if raw else "unset"),
                "masked": display,
            }
        else:
            out[key] = {
                "category": meta["category"],
                "label": meta["label"],
                "help": meta["help"],
                "secret": False,
                "value": raw,
                "source": "db" if _cache.get(key) else ("env" if raw else "unset"),
            }
    return out
