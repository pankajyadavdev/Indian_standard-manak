from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def list_audit_events(
    action: Optional[str] = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:read")),
):
    """Read recent audit records. This endpoint deliberately exposes no mutation."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    total = query.count()
    rows = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "events": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "user_email": row.user.email if row.user else None,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "ip_address": row.ip_address,
                "details": row.details,
                "timestamp": row.timestamp,
            }
            for row in rows
        ],
    }
