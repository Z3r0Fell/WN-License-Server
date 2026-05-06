"""Public unauthenticated routes (RSA pubkey, health)."""
from fastapi import APIRouter
from crypto_core import get_rsa_public_pem

router = APIRouter(tags=["public"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "watchnexus-license"}


@router.get("/public-key")
async def public_key():
    return {"pem": get_rsa_public_pem()}
