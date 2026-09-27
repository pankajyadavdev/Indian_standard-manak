import os
import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.audit import record_activity
from app.core.access import visible_document_query
from app.models.user import User
from app.models.project import Project
from app.models.document import Document
from app.models.audit import AuditLog
from app.api.deps import get_client_ip, require_permission
from app.schemas.document import DocumentResponse, DocumentDetailResponse, DocumentChunkResponse
from app.services.document_processor import (
    sanitize_filename,
    validate_file_content,
    compute_sha256,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_xlsx,
    extract_text_from_txt,
    normalize_text,
    chunk_text,
    DocumentValidationError
)
from app.services.embedding_service import vector_index

router = APIRouter(prefix="/documents", tags=["Document Processing Pipeline"])

# In-memory document chunks cache
document_chunks_store = {}


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    project_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("document:read")),
):
    """List documents in a project the current user is allowed to read."""
    project_query = db.query(Project).filter(Project.id == project_id, Project.is_deleted.is_(False))
    if not current_user.role or current_user.role.name != "admin":
        from sqlalchemy import or_
        scope = [Project.created_by_id == current_user.id]
        if current_user.department_id:
            scope.append(Project.department_id == current_user.department_id)
        project_query = project_query.filter(or_(*scope))
    if not project_query.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.is_deleted.is_(False))
        .order_by(Document.created_at.desc())
        .limit(100)
        .all()
    )

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    tender_id: Optional[str] = Form(None),
    current_user: User = Depends(require_permission("document:upload")),
    db: Session = Depends(get_db)
):
    """
    Complete Document Processing Pipeline:
    UPLOAD → VALIDATE → SECURITY SCAN → STORE → EXTRACT → OCR → NORMALIZE → CHUNK → METADATA → EMBEDDING → INDEX
    """
    ip_addr = get_client_ip(request)

    # Verify project exists
    project_query = db.query(Project).filter(Project.id == project_id, Project.is_deleted.is_(False))
    if not current_user.role or current_user.role.name != "admin":
        from sqlalchemy import or_
        scope = [Project.created_by_id == current_user.id]
        if current_user.department_id:
            scope.append(Project.department_id == current_user.department_id)
        project_query = project_query.filter(or_(*scope))
    project = project_query.first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found"
        )

    # 1. READ CONTENT
    max_upload_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    raw_content = await file.read(max_upload_bytes + 1)
    raw_filename = file.filename or "unknown_file.txt"

    # 2. VALIDATE (Format, Size, Magic Bytes)
    try:
        # Check size explicitly for 413
        if len(raw_content) > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
            )

        # Check extension for 415
        ext = os.path.splitext(raw_filename.lower())[1]
        if ext not in {".pdf", ".docx", ".xlsx", ".txt"}:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported format '{ext}'. Allowed: .pdf, .docx, .xlsx, .txt"
            )

        validated_ext = validate_file_content(raw_filename, raw_content, settings.MAX_UPLOAD_SIZE_MB)
    except DocumentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 3. SANITIZE FILENAME
    clean_filename = sanitize_filename(raw_filename)

    # 4. SECURITY SCAN (SHA-256 Content Hash)
    sha256_hash = compute_sha256(raw_content)
    document_id = str(uuid.uuid4())

    # 5. STORE FILE TO DISK
    storage_dir = os.path.join(settings.UPLOAD_DIR, project_id)
    os.makedirs(storage_dir, exist_ok=True)
    stored_name = f"{document_id}_{clean_filename}"
    file_path = os.path.join(storage_dir, stored_name)

    with open(file_path, "wb") as f:
        f.write(raw_content)

    # 6. EXTRACT & OCR
    ocr_applied = False
    total_pages = 1
    extracted_text = ""
    error_message = None

    try:
        if validated_ext == ".pdf":
            extracted_text, total_pages, ocr_applied = extract_text_from_pdf(raw_content)
        elif validated_ext == ".docx":
            extracted_text, total_pages = extract_text_from_docx(raw_content)
        elif validated_ext == ".xlsx":
            extracted_text, total_pages = extract_text_from_xlsx(raw_content)
        elif validated_ext == ".txt":
            extracted_text, total_pages = extract_text_from_txt(raw_content)
    except Exception as e:
        error_message = f"Text extraction failed: {str(e)}"
        extracted_text = ""

    # 7. NORMALIZE
    normalized_text = normalize_text(extracted_text)

    # 8. CHUNK
    chunks = chunk_text(normalized_text, document_id)
    document_chunks_store[document_id] = chunks

    # 9. EMBEDDING & INDEX (FAISS)
    if chunks:
        vector_index.add_chunks(chunks)

    # 10. SAVE TO DATABASE
    doc_record = Document(
        id=document_id,
        project_id=project_id,
        tender_id=tender_id,
        filename=clean_filename,
        stored_filename=stored_name,
        file_type=validated_ext.replace(".", ""),
        file_size_bytes=len(raw_content),
        file_hash_sha256=sha256_hash,
        processing_status="completed" if not error_message else "failed",
        ocr_applied=ocr_applied,
        extracted_text=normalized_text,
        total_pages=total_pages,
        error_message=error_message
    )
    db.add(doc_record)

    # 11. AUDIT LOG
    db.add(AuditLog(
        user_id=current_user.id,
        action="document.upload_and_process",
        entity_type="document",
        entity_id=document_id,
        ip_address=ip_addr,
        details=json.dumps({
            "filename": clean_filename,
            "size_bytes": len(raw_content),
            "sha256": sha256_hash,
            "ocr_applied": ocr_applied,
            "chunks_indexed": len(chunks)
        })
    ))
    db.commit()
    db.refresh(doc_record)

    return doc_record

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    request: Request,
    current_user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db)
):
    """Retrieve document metadata and text preview."""
    doc = visible_document_query(db, current_user).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    record_activity(db, request, current_user, "document.read", "document", doc.id)
    db.commit()

    chunks = document_chunks_store.get(document_id, [])
    preview = doc.extracted_text[:1000] if doc.extracted_text else ""

    return DocumentDetailResponse(
        id=doc.id,
        project_id=doc.project_id,
        tender_id=doc.tender_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        file_hash_sha256=doc.file_hash_sha256,
        processing_status=doc.processing_status,
        ocr_applied=doc.ocr_applied,
        total_pages=doc.total_pages,
        error_message=doc.error_message,
        created_at=doc.created_at,
        extracted_text_preview=preview,
        total_chunks=len(chunks)
    )

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
def get_document_chunks(
    document_id: str,
    request: Request,
    current_user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db)
):
    """Retrieve indexed chunks for a document."""
    doc = visible_document_query(db, current_user).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    record_activity(db, request, current_user, "document.chunks_read", "document", doc.id)
    db.commit()

    chunks = document_chunks_store.get(document_id, [])
    return [
        DocumentChunkResponse(
            chunk_index=c["chunk_index"],
            text=c["text"],
            page_number=c["page_number"],
            word_count=c["word_count"]
        ) for c in chunks
    ]
