"""Webhook signature verification utilities for Lemon Squeezy / Paddle / Gumroad."""
import hashlib
import hmac
import time


def verify_lemonsqueezy(body: bytes, signature_hdr: str, secret: str) -> bool:
    if not signature_hdr or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hdr.lower())


def verify_paddle(body: bytes, signature_hdr: str, secret: str,
                  max_age_seconds: int = 300) -> bool:
    if not signature_hdr or not secret:
        return False
    parts = dict(p.split("=", 1) for p in signature_hdr.split(";") if "=" in p)
    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False
    try:
        if abs(int(time.time()) - int(ts)) > max_age_seconds:
            return False
    except ValueError:
        return False
    payload = f"{ts}:".encode() + body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, h1)


def verify_gumroad(body: bytes, signature_hdr: str, secret: str) -> bool:
    if not signature_hdr or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hdr.lower())


def extract_email_lemonsqueezy(payload: dict) -> str | None:
    try:
        return payload.get("data", {}).get("attributes", {}).get("user_email") \
            or payload.get("meta", {}).get("custom_data", {}).get("email")
    except Exception:
        return None


def extract_email_paddle(payload: dict) -> str | None:
    try:
        d = payload.get("data", {})
        return d.get("customer", {}).get("email") or d.get("customer_email") \
            or d.get("email")
    except Exception:
        return None


def extract_email_gumroad(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("email")
    return None
