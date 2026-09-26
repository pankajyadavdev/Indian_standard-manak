import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin

class Standard(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "standards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    standard_code = Column(String(100), unique=True, nullable=False, index=True) # e.g. "IS 456", "IS 1786"
    title = Column(String(500), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True) # Civil, Electrical, Mechanical, Metallurgy, Chemical
    status = Column(String(50), default="active", nullable=False, index=True) # active, superseded, withdrawn, under_revision
    scope = Column(Text, nullable=True)
    bis_url = Column(String(500), nullable=True)

    versions = relationship("StandardVersion", back_populates="standard", cascade="all, delete-orphan", foreign_keys="[StandardVersion.standard_id]")
    certifications = relationship("Certification", back_populates="standard", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="standard")
    
    # Relationships where this standard is source or target
    outbound_references = relationship(
        "StandardReference",
        foreign_keys="[StandardReference.source_standard_id]",
        back_populates="source_standard",
        cascade="all, delete-orphan"
    )
    inbound_references = relationship(
        "StandardReference",
        foreign_keys="[StandardReference.target_standard_id]",
        back_populates="target_standard",
        cascade="all, delete-orphan"
    )

class StandardVersion(Base, TimestampMixin):
    __tablename__ = "standard_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    standard_id = Column(String(36), ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True) # e.g. 2000
    version_label = Column(String(100), nullable=False) # e.g. "IS 456:2000 (Fourth Revision)"
    is_current = Column(Boolean, default=True, nullable=False, index=True)
    effective_date = Column(DateTime, nullable=True)
    superseded_date = Column(DateTime, nullable=True)
    superseded_by_version_id = Column(String(36), ForeignKey("standard_versions.id"), nullable=True)
    changelog = Column(Text, nullable=True)

    standard = relationship("Standard", back_populates="versions", foreign_keys=[standard_id])
    amendments = relationship("Amendment", back_populates="standard_version", cascade="all, delete-orphan")
    superseded_by = relationship("StandardVersion", remote_side=[id])

class Amendment(Base, TimestampMixin):
    __tablename__ = "amendments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    standard_version_id = Column(String(36), ForeignKey("standard_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    amendment_number = Column(Integer, nullable=False) # 1, 2, 3...
    amendment_code = Column(String(100), nullable=False) # e.g. "Amendment No. 1 (May 2001)"
    issue_date = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    impact_clauses = Column(Text, nullable=True)

    standard_version = relationship("StandardVersion", back_populates="amendments")

class StandardReference(Base, TimestampMixin):
    __tablename__ = "standard_references"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_standard_id = Column(String(36), ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    target_standard_id = Column(String(36), ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True) 
    # normative, informative, test_method, safety, installation, terminology, material
    clause_reference = Column(String(100), nullable=True) # e.g. "Clause 5.3"
    description = Column(Text, nullable=True)

    source_standard = relationship("Standard", foreign_keys=[source_standard_id], back_populates="outbound_references")
    target_standard = relationship("Standard", foreign_keys=[target_standard_id], back_populates="inbound_references")
