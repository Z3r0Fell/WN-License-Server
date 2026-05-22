"""Public unauthenticated routes (RSA pubkey, health, branding)."""
from fastapi import APIRouter, Request

from crypto_core import get_rsa_public_pem
import runtime_settings

router = APIRouter(tags=["public"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "watchnexus-license"}


@router.get("/public-key")
async def public_key():
    return {"pem": get_rsa_public_pem()}


@router.get("/branding")
async def branding(request: Request):
    """Public branding info used by the landing page (portal link, brand name).
    Only non-secret keys are returned."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return {
        "brand_name": (runtime_settings.get("EMAIL_FROM_BRAND")
                       or runtime_settings.get("EMAIL_FROM_NAME")
                       or "WatchNexus"),
        "customer_portal_url": (runtime_settings.get("CUSTOMER_PORTAL_URL")
                                or f"{proto}://{host}/portal"),
        "app_public_url": (runtime_settings.get("APP_PUBLIC_URL")
                           or f"{proto}://{host}"),
    }
