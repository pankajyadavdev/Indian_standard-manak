import uuid
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin

class Recommendation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    tender_id = Column(String(36), ForeignKey("tenders.id", ondelete="SET NULL"), nullable=True, index=True)
    standard_id = Column(String(36), ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("standard_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    match_score = Column(Float, nullable=False, index=True) # 0.0 to 1.0
    confidence_level = Column(String(20), nullable=False) # High, Medium, Low
    
    # Explainable AI fields
    why_justification = Column(Text, nullable=False)
    relationship_summary = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    certification_status = Column(String(50), nullable=False) # Mandatory, Applicable, etc.
    
    status = Column(String(50), default="pending_review", nullable=False, index=True)
    # pending_review, accepted, rejected, flagged, review_requested

    project = relationship("Project", back_populates="recommendations")
    tender = relationship("Tender", back_populates="recommendations")
    standard = relationship("Standard", back_populates="recommendations")
    version = relationship("StandardVersion")
    evidence_items = relationship("Evidence", back_populates="recommendation", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="recommendation", cascade="all, delete-orphan")

class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_id = Column(String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    standard_id = Column(String(36), ForeignKey("standards.id", ondelete="SET NULL"), nullable=True, index=True)
    
    source_text_snippet = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    clause_number = Column(String(100), nullable=True)
    confidence_score = Column(Float, nullable=False)
    evidence_type = Column(String(50), nullable=False, index=True)
    # tender_requirement, standard_clause, test_requirement, certification_order

    recommendation = relationship("Recommendation", back_populates="evidence_items")
    document = relationship("Document", back_populates="evidence_items")
    standard = relationship("Standard")
