import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin

class Certification(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "certifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    standard_id = Column(String(36), ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    certification_type = Column(String(100), nullable=False, index=True) # "ISI Mark - Scheme I", "CRS", "BIS Hallmark"
    is_mandatory = Column(Boolean, default=False, nullable=False, index=True)
    qco_order_number = Column(String(255), nullable=True) # e.g. "S.O. 1234(E)"
    qco_date = Column(DateTime, nullable=True)
    applicable_ministry = Column(String(255), nullable=True) # e.g. "Ministry of Steel", "DPIIT", "MeitY"
    compliance_category = Column(String(50), nullable=False, index=True)
    # Mandatory, Applicable, Potentially applicable, Not identified, Manual verification required
    details = Column(Text, nullable=True)

    standard = relationship("Standard", back_populates="certifications")
