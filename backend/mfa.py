"""Multi-factor auth + admin-login IP allowlist helpers.

TOTP via pyotp (RFC 6238). Recovery codes are stored bcrypt-hashed so they
can never be read back, only verified.
"""
from __future__ import annotations

import base64
import io
import secrets
import string
from typing import List, Optional

import bcrypt
import pyotp
import qrcode

import runtime_settings as rs
from webhooks_sig import ip_in_allowlist


# ---------------------------------------------------------------------------
# TOTP helpers
# ---------------------------------------------------------------------------
ISSUER = "WatchNexus"


def new_secret() -> str:
    """Generate a fresh base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str, issuer: Optional[str] = None) -> str:
    """Return otpauth:// URI suitable for embedding in a QR code."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email,
        issuer_name=issuer or ISSUER,
    )


def qr_png_data_uri(uri: str) -> str:
    """Render a QR code as a base64-encoded PNG data URI (browser-renderable)."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code allowing +/- 1 step of clock skew by default."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Recovery codes (one-time use, bcrypt-hashed at rest)
# ---------------------------------------------------------------------------
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LEN = 10  # base32-like chars, grouped for readability


def _gen_one_recovery() -> str:
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(RECOVERY_CODE_LEN))
    # Group in 5s for readability: XXXXX-XXXXX
    return f"{raw[:5]}-{raw[5:]}"


def new_recovery_codes() -> List[str]:
    """Generate a fresh batch of plaintext recovery codes (show ONCE to user)."""
    return [_gen_one_recovery() for _ in range(RECOVERY_CODE_COUNT)]


def hash_recovery_codes(codes: List[str]) -> List[str]:
    """bcrypt-hash each code so it can be stored safely."""
    return [bcrypt.hashpw(c.encode(), bcrypt.gensalt(rounds=10)).decode() for c in codes]


def consume_recovery_code(hashed_codes: List[str], candidate: str) -> Optional[List[str]]:
    """If `candidate` matches one of the stored hashes, return the new list with
    that hash removed (one-time use). Returns None on no match."""
    if not candidate or not hashed_codes:
        return None
    candidate_norm = candidate.strip().upper().replace(" ", "")
    # Accept both "XXXXX-XXXXX" and "XXXXXXXXXX" formats.
    for normalize in (candidate_norm, candidate_norm.replace("-", "")):
        for i, h in enumerate(hashed_codes):
            try:
                if bcrypt.checkpw(normalize.encode(), h.encode()):
                    return hashed_codes[:i] + hashed_codes[i + 1:]
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# IP allowlist for /admin/login
# ---------------------------------------------------------------------------
def admin_login_ip_allowed(ip: Optional[str]) -> bool:
    """Returns True if the IP is allowed to attempt admin login.
    Blank/missing allowlist setting means "allow everyone"."""
    raw = (rs.get("ADMIN_LOGIN_IP_ALLOWLIST") or "").strip()
    if not raw:
        return True
    allowlist = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    if not allowlist:
        return True
    return ip_in_allowlist(ip, allowlist)
