from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class TimestampMixin:
    """Provides created_at and updated_at timestamp columns."""
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

class SoftDeleteMixin:
    """Provides is_deleted and deleted_at columns for recoverable deletion."""
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
