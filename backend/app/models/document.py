import uuid
from sqlalchemy import Column, String, Text, BigInteger, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin

class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tender_id = Column(String(36), ForeignKey("tenders.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf, docx, xlsx, txt
    file_size_bytes = Column(BigInteger, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False, index=True)
    
    processing_status = Column(String(50), default="pending", nullable=False, index=True) # pending, scanning, parsing, completed, failed
    ocr_applied = Column(Boolean, default=False, nullable=False)
    extracted_text = Column(Text, nullable=True)
    total_pages = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    project = relationship("Project", back_populates="documents")
    tender = relationship("Tender", back_populates="documents")
    evidence_items = relationship("Evidence", back_populates="document", cascade="all, delete-orphan")
