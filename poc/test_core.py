"""
WatchNexus Licensing Server - Core POC
=======================================
Proves the cryptographic core works in isolation before app development.

Tests:
1. HMAC license key generation + verification (forgery-proof)
2. RSA license key generation + verification (asymmetric, offline verifiable)
3. Activation token issuance + validation with offline grace period
4. Webhook signature verification for:
   - Stripe (HMAC-SHA256 of `{t}.{body}` with header `Stripe-Signature: t=...;v1=...`)
5. Fingerprint binding logic (HW + Domain modes)

Run: `python test_core.py`
"""
import base64
import hmac
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


# ---------------------------------------------------------------------------
# 1. License key generation & verification
# ---------------------------------------------------------------------------
# Format: WNX-<base32 of payload>-<base32 of sig>
#   payload = JSON {"id": "<license_id>", "p": "<product_id>", "iat": ts}
# HMAC version uses shared secret. RSA version signs payload with PRIVATE,
# verification uses PUBLIC (so client apps can verify offline).

def _b32encode(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip("=")


def _b32decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 8)
    return base64.b32decode(s + pad)


def generate_hmac_license(license_id: str, product_id: str, secret: bytes) -> str:
    payload = {"id": license_id, "p": product_id, "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret, raw, hashlib.sha256).digest()
    return f"WNX-{_b32encode(raw)}-{_b32encode(sig)}"


def verify_hmac_license(key: str, secret: bytes) -> dict | None:
    try:
        prefix, payload_b32, sig_b32 = key.split("-", 2)
        if prefix != "WNX":
            return None
        raw = _b32decode(payload_b32)
        sig = _b32decode(sig_b32)
        expected = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(raw)
    except Exception:
        return None


def generate_rsa_license(license_id: str, product_id: str, private_key) -> str:
    payload = {"id": license_id, "p": product_id, "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = private_key.sign(
        raw,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return f"WNX-{_b32encode(raw)}-{_b32encode(sig)}"


def verify_rsa_license(key: str, public_key) -> dict | None:
    try:
        prefix, payload_b32, sig_b32 = key.split("-", 2)
        if prefix != "WNX":
            return None
        raw = _b32decode(payload_b32)
        sig = _b32decode(sig_b32)
        public_key.verify(
            sig,
            raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return json.loads(raw)
    except Exception:
        return None


def test_hmac_license():
    secret = secrets.token_bytes(32)
    key = generate_hmac_license("lic_abc123", "prod_watchnexus", secret)
    assert key.startswith("WNX-"), "license key prefix wrong"
    parsed = verify_hmac_license(key, secret)
    assert parsed and parsed["id"] == "lic_abc123" and parsed["p"] == "prod_watchnexus"

    # Forgery: tamper sig
    bad = key[:-4] + "AAAA"
    assert verify_hmac_license(bad, secret) is None, "tampered sig accepted!"

    # Wrong secret
    other_secret = secrets.token_bytes(32)
    assert verify_hmac_license(key, other_secret) is None, "wrong secret accepted!"
    print("✓ HMAC license generation/verification works")


def test_rsa_license():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    key = generate_rsa_license("lic_xyz789", "prod_watchnexus", priv)
    parsed = verify_rsa_license(key, pub)
    assert parsed and parsed["id"] == "lic_xyz789"

    # Different keypair fails
    other_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert verify_rsa_license(key, other_priv.public_key()) is None
    print("✓ RSA license generation/verification works")

    # Public key can be exported (so clients can verify offline)
    pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert pem.startswith(b"-----BEGIN PUBLIC KEY-----")
    print("✓ RSA public key exportable for offline client verification")


# ---------------------------------------------------------------------------
# 2. Activation token with offline grace period
# ---------------------------------------------------------------------------
# After /activate succeeds, the server returns a JWT with:
#   sub: license_id, fp: fingerprint hash, exp: short (e.g., 24h),
#   grace_until: extended (e.g., 7d) so brief network blips don't lock users
# Client treats token as valid if (now <= exp) OR (now <= grace_until and signature valid).

ACTIVATION_TOKEN_TTL = 60 * 60 * 24          # 24h online
ACTIVATION_TOKEN_GRACE = 60 * 60 * 24 * 7    # +7d offline grace


def issue_activation_token(license_id: str, fingerprint: str, secret: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": license_id,
            "fp": fingerprint,
            "iat": now,
            "exp": now + ACTIVATION_TOKEN_TTL,
            "grace_until": now + ACTIVATION_TOKEN_TTL + ACTIVATION_TOKEN_GRACE,
            "iss": "watchnexus-license",
        },
        secret,
        algorithm="HS256",
    )


def validate_activation_token(token: str, secret: str, expected_fp: str) -> dict:
    """Returns dict with `valid`, `mode` (online|grace|expired), and decoded claims."""
    # Decode without exp verification so we can decide grace ourselves
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
            issuer="watchnexus-license",
        )
    except jwt.InvalidTokenError as e:
        return {"valid": False, "mode": "invalid", "reason": str(e)}

    if claims.get("fp") != expected_fp:
        return {"valid": False, "mode": "fingerprint_mismatch"}

    now = int(time.time())
    if now <= claims["exp"]:
        return {"valid": True, "mode": "online", "claims": claims}
    if now <= claims.get("grace_until", 0):
        return {"valid": True, "mode": "grace", "claims": claims}
    return {"valid": False, "mode": "expired", "claims": claims}


def test_activation_token():
    secret = "test-jwt-secret"
    fp = hashlib.sha256(b"hwid:abc-mac:xx-domain:example.com").hexdigest()
    token = issue_activation_token("lic_abc", fp, secret)

    r = validate_activation_token(token, secret, fp)
    assert r["valid"] and r["mode"] == "online"

    # Wrong fingerprint
    r = validate_activation_token(token, secret, "different")
    assert not r["valid"] and r["mode"] == "fingerprint_mismatch"

    # Wrong secret
    r = validate_activation_token(token, "other-secret", fp)
    assert not r["valid"] and r["mode"] == "invalid"

    # Simulate token past exp but within grace by issuing one in the past
    now = int(time.time())
    past_token = jwt.encode(
        {
            "sub": "lic_abc",
            "fp": fp,
            "iat": now - 100_000,
            "exp": now - 1000,                   # already expired
            "grace_until": now + 60 * 60 * 24,   # still in grace
            "iss": "watchnexus-license",
        },
        secret,
        algorithm="HS256",
    )
    r = validate_activation_token(past_token, secret, fp)
    assert r["valid"] and r["mode"] == "grace", f"grace failed: {r}"

    # Past grace
    dead_token = jwt.encode(
        {
            "sub": "lic_abc",
            "fp": fp,
            "iat": now - 1_000_000,
            "exp": now - 100_000,
            "grace_until": now - 10_000,
            "iss": "watchnexus-license",
        },
        secret,
        algorithm="HS256",
    )
    r = validate_activation_token(dead_token, secret, fp)
    assert not r["valid"] and r["mode"] == "expired"
    print("✓ Activation token + offline grace period works")


# ---------------------------------------------------------------------------
# 3. Fingerprint binding
# ---------------------------------------------------------------------------
def compute_fingerprint(mode: str, hw_id: str | None = None, domain: str | None = None) -> str:
    parts = []
    if mode in ("hw", "both") and hw_id:
        parts.append(f"hw:{hw_id}")
    if mode in ("domain", "both") and domain:
        parts.append(f"domain:{domain.lower()}")
    if mode == "none" or not parts:
        parts = ["any"]
    raw = "|".join(parts).encode()
    return hashlib.sha256(raw).hexdigest()


def test_fingerprint():
    fp_hw = compute_fingerprint("hw", hw_id="MAC:AABBCC", domain=None)
    fp_dom = compute_fingerprint("domain", hw_id=None, domain="customer.com")
    fp_both = compute_fingerprint("both", hw_id="MAC:AABBCC", domain="customer.com")
    fp_none = compute_fingerprint("none")
    assert fp_hw != fp_dom != fp_both
    assert len(fp_hw) == 64 and len(fp_none) == 64
    # Domain casing normalized
    assert compute_fingerprint("domain", domain="Customer.COM") == fp_dom
    print("✓ Fingerprint binding (HW/Domain/Both/None) works")


# ---------------------------------------------------------------------------
# 4. Webhook signature verification (Stripe)
# ---------------------------------------------------------------------------
def verify_stripe(body: bytes, signature_hdr: str, secret: str, max_age_seconds: int = 300) -> bool:
    """Stripe: `Stripe-Signature` is `t=...;v1=...`. v1 = HMAC-SHA256(secret, "{t}.{body}")."""
    if not signature_hdr:
        return False
    parts = dict(p.split("=", 1) for p in signature_hdr.split(",") if "=" in p)
    ts = parts.get("t")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False
    if abs(int(time.time()) - int(ts)) > max_age_seconds:
        return False
    payload = f"{ts}.".encode() + body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def test_webhooks():
    secret_st = "whsec_test_secret"
    body_st = json.dumps({
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {"object": {"customer_email": "buyer@example.com", "id": "cs_1"}},
    }).encode()
    ts = str(int(time.time()))
    v1 = hmac.new(secret_st.encode(), f"{ts}.".encode() + body_st, hashlib.sha256).hexdigest()
    sig_st = f"t={ts},v1={v1}"
    assert verify_stripe(body_st, sig_st, secret_st)
    assert not verify_stripe(body_st, sig_st, "wrong")
    # Replay too old
    old_ts = str(int(time.time()) - 10_000)
    old_v1 = hmac.new(secret_st.encode(), f"{old_ts}.".encode() + body_st, hashlib.sha256).hexdigest()
    assert not verify_stripe(body_st, f"t={old_ts},v1={old_v1}", secret_st)
    print("✓ Stripe webhook signature verification (with replay protection) works")


# ---------------------------------------------------------------------------
# 5. End-to-end: simulate full activate/validate flow
# ---------------------------------------------------------------------------
def test_e2e_flow():
    # Server bootstraps: HMAC secret + RSA keypair + JWT secret
    hmac_secret = secrets.token_bytes(32)
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwt_secret = "watchnexus-jwt-secret"

    # Admin issues a license (HMAC product)
    license_id = "lic_e2e_001"
    product_id = "prod_watchnexus"
    license_key = generate_hmac_license(license_id, product_id, hmac_secret)
    assert verify_hmac_license(license_key, hmac_secret)

    # Client app: fingerprint computed from HW+Domain
    fp = compute_fingerprint("both", hw_id="MAC:AA:BB:CC:DD", domain="acme.com")

    # Server /activate: verifies license_key, binds to fp, issues activation token
    parsed = verify_hmac_license(license_key, hmac_secret)
    assert parsed["id"] == license_id
    token = issue_activation_token(license_id, fp, jwt_secret)

    # Client offline /validate
    r = validate_activation_token(token, jwt_secret, fp)
    assert r["valid"] and r["mode"] == "online"
    print("✓ End-to-end activate→validate flow works")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("WatchNexus Licensing Server — Core POC")
    print("=" * 50)
    test_hmac_license()
    test_rsa_license()
    test_activation_token()
    test_fingerprint()
    test_webhooks()
    test_e2e_flow()
    print("=" * 50)
    print("ALL CORE TESTS PASSED ✓")
