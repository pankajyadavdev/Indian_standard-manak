import uuid
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin

class Project(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False, index=True) # draft, processing, analyzed, in_review, approved, rejected
    
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True, index=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    department = relationship("Department", back_populates="projects")
    creator = relationship("User", back_populates="projects")
    tenders = relationship("Tender", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="project", cascade="all, delete-orphan")

class Tender(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    tender_number = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    issuing_authority = Column(String(255), nullable=False, index=True)
    estimated_value = Column(Float, nullable=True)
    currency = Column(String(10), default="INR", nullable=False)
    submission_deadline = Column(DateTime, nullable=True)
    status = Column(String(50), default="active", nullable=False, index=True)

    project = relationship("Project", back_populates="tenders")
    documents = relationship("Document", back_populates="tender", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="tender", cascade="all, delete-orphan")
