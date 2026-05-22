"""
WatchNexus Licensing Server - drop-in Python client.

Usage:
    from watchnexus_client import WatchNexusClient

    client = WatchNexusClient(
        base_url="https://licenses.example.com",
        api_key="wnk_...",
        license_key="WNX-...",
    )

    token = client.activate(hardware_id="01:23:45:67:89:AB",
                            domain="customer.example.com",
                            device_name="Marie’s MacBook Pro")
    # token is a dict with activation_token, expires_at, grace_until, ...

    state = client.validate(token, hardware_id=..., domain=...)
    # state is a dict { valid: bool, mode: str, license: ..., activation: ... }

    # When offline, client.validate falls through to local grace-period check
    # so brief network blips never lock a paying user out.

    client.deactivate(token)

Only stdlib + requests. MIT-licensed; copy it into your codebase.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import requests  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "watchnexus_client requires `requests`. Install with: pip install requests"
    ) from exc


class WatchNexusError(Exception):
    """Raised for non-2xx responses from the licensing server."""

    def __init__(self, message: str, status: Optional[int] = None,
                 payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass
class WatchNexusClient:
    base_url: str
    api_key: str
    license_key: Optional[str] = None
    timeout: float = 10.0
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "watchnexus-python/1.0",
        })

    # -------------------- public API --------------------
    def activate(self, hardware_id: Optional[str] = None,
                  domain: Optional[str] = None,
                  device_name: Optional[str] = None,
                  license_key: Optional[str] = None) -> dict:
        key = license_key or self.license_key
        if not key:
            raise ValueError("license_key required (pass it or set client.license_key)")
        body = {"license_key": key, "hardware_id": hardware_id,
                "domain": domain, "device_name": device_name}
        return self._post("/api/integrate/activate", body)

    def validate(self, token: dict | str, hardware_id: Optional[str] = None,
                  domain: Optional[str] = None,
                  allow_offline_grace: bool = True) -> dict:
        """Validate against the server. If the network call fails AND the local
        token is still within its `grace_until`, returns { valid: True, mode: 'grace_offline' }."""
        activation_token = token["activation_token"] if isinstance(token, dict) else token
        body = {"activation_token": activation_token,
                "hardware_id": hardware_id, "domain": domain}
        try:
            return self._post("/api/integrate/validate", body)
        except (requests.RequestException, WatchNexusError) as e:
            if allow_offline_grace:
                local = decode_activation_token_locally(activation_token)
                if local and local.get("grace_until", 0) >= int(time.time()):
                    return {"valid": True, "mode": "grace_offline",
                            "claims": local, "error": str(e)}
            raise

    def deactivate(self, token: dict | str,
                    hardware_id: Optional[str] = None,
                    domain: Optional[str] = None) -> dict:
        if isinstance(token, dict):
            activation_token = token.get("activation_token")
        else:
            activation_token = token
        body = {"activation_token": activation_token,
                "license_key": self.license_key,
                "hardware_id": hardware_id, "domain": domain}
        return self._post("/api/integrate/deactivate", body)

    def public_key(self) -> str:
        r = self.session.get(f"{self.base_url}/api/public-key", timeout=self.timeout)
        r.raise_for_status()
        return r.json()["pem"]

    def health(self) -> dict:
        r = self.session.get(f"{self.base_url}/api/health", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # -------------------- internals --------------------
    def _post(self, path: str, body: dict) -> dict:
        r = self.session.post(f"{self.base_url}{path}",
                              data=json.dumps(body), timeout=self.timeout)
        if r.status_code >= 400:
            try:
                payload = r.json()
            except Exception:
                payload = r.text
            raise WatchNexusError(
                f"{path} failed: {r.status_code}", status=r.status_code, payload=payload,
            )
        return r.json()


# ---------------------------------------------------------------------------
# Local helpers (no network) for offline grace handling.
# ---------------------------------------------------------------------------

def decode_activation_token_locally(token: str) -> Optional[dict]:
    """Decode (but do NOT cryptographically verify) the JWT payload so a
    client can fall back to grace-period checks while offline. Always
    pair this with a successful prior /activate against the server."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        pad = "=" * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(parts[1] + pad)
        return json.loads(payload)
    except Exception:
        return None


def verify_license_key_hmac(license_key: str, shared_secret: bytes) -> Optional[dict]:
    """For HMAC-signed licenses, verify the key locally with the same secret
    your server uses (advanced; only useful if you embed the secret in a
    trusted environment)."""
    try:
        prefix, payload_b32, sig_b32 = license_key.split("-", 2)
        if prefix != "WNX":
            return None
        raw = _b32decode(payload_b32)
        sig = _b32decode(sig_b32)
        expected = hmac.new(shared_secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(raw)
    except Exception:
        return None


def _b32decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 8)
    return base64.b32decode(s + pad)
