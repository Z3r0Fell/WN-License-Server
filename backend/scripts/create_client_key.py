"""Create the publishable WatchNexus client key (activate/validate/deactivate
only — it can never mint serials) and optionally revoke an old key by hash.

Run inside the backend container on the VPS:

    cd /opt/watchnexus/deploy
    docker compose exec backend python scripts/create_client_key.py
    docker compose exec backend python scripts/create_client_key.py \
        --revoke-hash <sha256-of-old-key>

The raw key is printed ONCE. Pass it to the WatchNexus image build:
    docker build --build-arg LICENSE_SERVER_CLIENT_KEY=<key> ...
"""
import argparse
import asyncio
import hashlib
import secrets
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import db, now_iso  # noqa: E402

CLIENT_SCOPES = ["activate", "validate", "deactivate"]


async def main(args) -> int:
    if args.revoke_hash:
        res = await db.api_keys.update_many(
            {"key_hash": args.revoke_hash.strip().lower(), "status": "active"},
            {"$set": {"status": "revoked", "revoked_at": now_iso()}})
        print(f"revoked {res.modified_count} key(s) matching hash")
    if args.revoke_only:
        return 0

    raw = "wnk_" + secrets.token_urlsafe(32)
    await db.api_keys.insert_one({
        "id": str(uuid.uuid4()),
        "name": args.name,
        "product_id": None,
        "scopes": CLIENT_SCOPES,
        "allowed_ips": [],
        "key": raw,
        "key_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "is_bootstrap": False,
        "status": "active",
        "created_at": now_iso(),
        "last_used_at": None,
        "last_used_ip": None,
    })
    print(f"scopes : {', '.join(CLIENT_SCOPES)}")
    print(f"key    : {raw}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="WatchNexus client (public, activate-only)")
    p.add_argument("--revoke-hash", help="sha256 hex of a key to revoke first")
    p.add_argument("--revoke-only", action="store_true", help="revoke without creating a key")
    sys.exit(asyncio.run(main(p.parse_args())))
