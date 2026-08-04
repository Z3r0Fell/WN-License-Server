"""Cryptographic core (ported from POC test_core.py).
Handles license signing/verification (HMAC + RSA), activation tokens with offline grace,
and fingerprint hashing."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


# ---- License key encoding helpers ----
def _b32encode(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip("=")


def _b32decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 8)
    return base64.b32decode(s + pad)


# ---- Short serial (v2) ----
# Format: WNX-<TIER>-XXXX-XXXX-XXXX (22 chars). No embedded signature — the
# server validates the key against the DB on activation. The WatchNexus client
# only trusts the license server's response, so a compact unguessable key is
# sufficient (60-bit random payload).
def license_tier_prefix(plan: str | None) -> str:
    """Derive a human tier prefix from a plan name (mirrors WatchNexus plan→tier)."""
    p = (plan or "").lower()
    if "ult" in p:
        return "ULT"
    if "pro" in p:
        return "PRO"
    return "STD"


def generate_license_key(plan: str = "standard") -> str:
    """Generate a 22-char serial: WNX-<TIER>-XXXX-XXXX-XXXX."""
    raw = _b32encode(secrets.token_bytes(8)).upper()[:12]
    groups = "-".join(raw[i:i + 4] for i in range(0, 12, 4))
    return f"WNX-{license_tier_prefix(plan)}-{groups}"


def is_short_license_key(key: str) -> bool:
    """Format check for the short serial (no signature verification)."""
    try:
        prefix, tier, g1, g2, g3 = key.split("-")
    except (ValueError, AttributeError):
        return False
    return (prefix == "WNX" and len(tier) == 3 and
            all(len(g) == 4 for g in (g1, g2, g3)))


# ---- HMAC license ----
def generate_hmac_license(license_id: str, product_id: str, secret: bytes) -> str:
    payload = {"id": license_id, "p": product_id, "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret, raw, hashlib.sha256).digest()
    return f"WNX-{_b32encode(raw)}-{_b32encode(sig)}"


def verify_hmac_license(key: str, secret: bytes) -> Optional[dict]:
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


# ---- RSA license ----
_rsa_private_cache = None
_rsa_public_cache = None


def _load_rsa_keys():
    global _rsa_private_cache, _rsa_public_cache
    if _rsa_private_cache and _rsa_public_cache:
        return _rsa_private_cache, _rsa_public_cache
    priv_path = Path(os.environ.get("RSA_PRIVATE_KEY_PATH", "/app/backend/keys/license_rsa_private.pem"))
    pub_path = Path(os.environ.get("RSA_PUBLIC_KEY_PATH", "/app/backend/keys/license_rsa_public.pem"))
    if not priv_path.exists() or not pub_path.exists():
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_path.parent.mkdir(parents=True, exist_ok=True)
        priv_path.write_bytes(priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        pub_path.write_bytes(priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    priv = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    pub = serialization.load_pem_public_key(pub_path.read_bytes())
    _rsa_private_cache, _rsa_public_cache = priv, pub
    return priv, pub


def get_rsa_public_pem() -> str:
    _, pub = _load_rsa_keys()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def generate_rsa_license(license_id: str, product_id: str) -> str:
    priv, _ = _load_rsa_keys()
    payload = {"id": license_id, "p": product_id, "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = priv.sign(
        raw,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return f"WNX-{_b32encode(raw)}-{_b32encode(sig)}"


def verify_rsa_license(key: str) -> Optional[dict]:
    _, pub = _load_rsa_keys()
    try:
        prefix, payload_b32, sig_b32 = key.split("-", 2)
        if prefix != "WNX":
            return None
        raw = _b32decode(payload_b32)
        sig = _b32decode(sig_b32)
        pub.verify(
            sig, raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return json.loads(raw)
    except Exception:
        return None


# ---- Activation token ----
ACTIVATION_TOKEN_TTL = 60 * 60 * 24  # 24h online
ACTIVATION_TOKEN_GRACE = 60 * 60 * 24 * 7  # +7d offline grace


def _jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "dev-secret-please-change")


def issue_activation_token(license_id: str, fingerprint: str, activation_id: str,
                           ttl: int = ACTIVATION_TOKEN_TTL,
                           grace: int = ACTIVATION_TOKEN_GRACE) -> dict:
    now = int(time.time())
    claims = {
        "sub": license_id,
        "aid": activation_id,
        "fp": fingerprint,
        "iat": now,
        "exp": now + ttl,
        "grace_until": now + ttl + grace,
        "iss": "watchnexus-license",
    }
    token = jwt.encode(claims, _jwt_secret(), algorithm="HS256")
    return {"token": token, **claims}


def validate_activation_token(token: str, expected_fp: Optional[str] = None) -> dict:
    try:
        claims = jwt.decode(
            token, _jwt_secret(), algorithms=["HS256"],
            options={"verify_exp": False}, issuer="watchnexus-license",
        )
    except jwt.InvalidTokenError as e:
        return {"valid": False, "mode": "invalid", "reason": str(e)}
    if expected_fp is not None and claims.get("fp") != expected_fp:
        return {"valid": False, "mode": "fingerprint_mismatch"}
    now = int(time.time())
    if now <= claims.get("exp", 0):
        return {"valid": True, "mode": "online", "claims": claims}
    if now <= claims.get("grace_until", 0):
        return {"valid": True, "mode": "grace", "claims": claims}
    return {"valid": False, "mode": "expired", "claims": claims}


# ---- Fingerprint ----
def compute_fingerprint(mode: str, hw_id: Optional[str] = None,
                       domain: Optional[str] = None) -> str:
    parts = []
    if mode in ("hw", "both") and hw_id:
        parts.append(f"hw:{hw_id}")
    if mode in ("domain", "both") and domain:
        parts.append(f"domain:{domain.lower()}")
    if mode == "none" or not parts:
        parts = ["any"]
    raw = "|".join(parts).encode()
    return hashlib.sha256(raw).hexdigest()
