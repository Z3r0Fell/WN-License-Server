"""Audit log helper."""
import uuid
from typing import Any

from db import db, now_iso


async def log(actor_type: str, actor_id: str | None, actor_email: str | None,
              action: str, target_type: str | None = None,
              target_id: str | None = None, severity: str = "info",
              meta: dict[str, Any] | None = None,
              ip: str | None = None) -> None:
    doc = {
        "id": str(uuid.uuid4()),
        "ts": now_iso(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_email": actor_email,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "severity": severity,
        "meta": meta or {},
        "ip": ip,
    }
    await db.audit_log.insert_one(doc)
