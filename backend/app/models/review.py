import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin

class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_id = Column(String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    action = Column(String(50), nullable=False, index=True)
    # accept, reject, flag, comment, request_review
    comments = Column(Text, nullable=True)
    reason_code = Column(String(100), nullable=True, index=True)
    # e.g., "technical_mismatch", "superseded_version", "mandatory_compliance_met", "other"

    recommendation = relationship("Recommendation", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")
