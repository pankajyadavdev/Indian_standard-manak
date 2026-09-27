import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.models.audit import AuditLog
from app.models.user import User


def record_activity(
    db: Session,
    request: Request,
    user: User,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Add a privacy-conscious activity event to the current transaction."""
    db.add(AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "unknown")[:255],
        details=json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
    ))
