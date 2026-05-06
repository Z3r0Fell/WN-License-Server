"""Webhook signature verification utilities for Lemon Squeezy / Paddle / Gumroad / Stripe."""
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


def verify_stripe(body: bytes, signature_hdr: str, secret: str,
                  max_age_seconds: int = 300) -> bool:
    """Stripe-Signature: t=<ts>,v1=<hex>(,v0=...). HMAC-SHA256(secret, '{t}.{body}')."""
    if not signature_hdr or not secret:
        return False
    parts = {}
    for token in signature_hdr.split(","):
        if "=" in token:
            k, v = token.split("=", 1)
            parts.setdefault(k.strip(), []).append(v.strip())
    ts_list = parts.get("t")
    sigs = parts.get("v1", [])
    if not ts_list or not sigs:
        return False
    ts = ts_list[0]
    try:
        if abs(int(time.time()) - int(ts)) > max_age_seconds:
            return False
    except ValueError:
        return False
    payload = f"{ts}.".encode() + body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


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


def extract_email_stripe(payload: dict) -> str | None:
    try:
        obj = payload.get("data", {}).get("object", {}) or {}
        return (obj.get("customer_email")
                or obj.get("customer_details", {}).get("email")
                or obj.get("receipt_email")
                or obj.get("billing_details", {}).get("email"))
    except Exception:
        return None


def ip_in_allowlist(ip: str | None, allowlist: list[str] | None) -> bool:
    """Returns True if no allowlist (allow all) OR ip is in any of the allowed entries.
    Entries can be exact IPs, CIDR ranges (v4 or v6), or '*' which means allow-all."""
    if not allowlist:
        return True
    if not ip:
        return False
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        e = (entry or "").strip()
        if not e or e == "*":
            return True
        try:
            if "/" in e:
                if addr in ipaddress.ip_network(e, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(e):
                    return True
        except ValueError:
            continue
    return False
