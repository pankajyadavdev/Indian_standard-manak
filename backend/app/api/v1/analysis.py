import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.standard import Standard
from app.models.audit import AuditLog
from app.api.deps import get_current_user, get_client_ip
from app.schemas.specification import SpecificationExtractionRequest, SpecificationExtractionResponse
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.entity_extractor import extract_entities
from app.services.rag_engine import rag_engine, INSUFFICIENT_EVIDENCE_MSG
from app.services.certification_engine import certification_engine

router = APIRouter(prefix="/analysis", tags=["Specification Analysis & Extraction"])

@router.post("/rag-explain", response_model=RAGQueryResponse)
def rag_explain(
    req: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evidence-Grounded RAG Endpoint:
    The system can ONLY explain retrieved evidence.
    If evidence is absent, strictly returns 'Insufficient verified evidence.'
    """
    rag_res = rag_engine.generate_grounded_explanation(
        db=db,
        query=req.query,
        document_id=req.document_id
    )
    return RAGQueryResponse(**rag_res.to_dict())

@router.post("/certification-check")
def certification_check(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluate one or more standard codes for certification compliance (QCO/BIS rules).
    Supply optional tender_clause_text to test for explicit ISI mark requirement.
    """
    standards = payload.get("standards", [])
    tender_text = payload.get("tender_clause_text", None)
    if not standards:
        raise HTTPException(status_code=400, detail="'standards' list is required.")
    return certification_engine.evaluate_tender(db, standards, tender_text)

@router.post("/extract-specifications", response_model=SpecificationExtractionResponse)
def extract_specifications(
    req: SpecificationExtractionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract structured specification entities from an uploaded document or custom text:
    Product, Category, Material, Dimensions, Capacity, Performance, Application,
    Environment, Safety, Testing, Installation, Certification Hints.
    """
    ip_addr = get_client_ip(request)
    text_to_analyze = ""

    if req.document_id:
        doc = db.query(Document).filter(Document.id == req.document_id, Document.is_deleted == False).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        text_to_analyze = doc.extracted_text or ""
    elif req.custom_text:
        text_to_analyze = req.custom_text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either document_id or custom_text must be provided"
        )

    if not text_to_analyze.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document or provided text contains no readable content"
        )

    entities = extract_entities(text_to_analyze)

    # Check database for cited standards
    matched_standards = 0
    for std_code in entities.standards_cited:
        # Match base code (e.g. "IS 456" from "IS 456:2000")
        base_code = std_code.split(":")[0].strip()
        found = db.query(Standard).filter(Standard.standard_code.ilike(f"{base_code}%")).first()
        if found:
            matched_standards += 1

    total_entities = (
        len(entities.products) +
        len(entities.categories) +
        len(entities.materials) +
        len(entities.dimensions) +
        len(entities.capacities) +
        len(entities.performance) +
        len(entities.applications) +
        len(entities.environments) +
        len(entities.safety) +
        len(entities.testing) +
        len(entities.installation) +
        len(entities.certification_hints) +
        len(entities.standards_cited)
    )

    db.add(AuditLog(
        user_id=current_user.id,
        action="ai.specification_extracted",
        entity_type="document" if req.document_id else "custom_text",
        entity_id=req.document_id,
        ip_address=ip_addr,
        details=json.dumps({
            "total_entities": total_entities,
            "standards_cited": entities.standards_cited,
            "confidence": entities.confidence_score
        })
    ))
    db.commit()

    return SpecificationExtractionResponse(
        document_id=req.document_id,
        entities=entities,
        total_entities_found=total_entities,
        standards_matched_count=matched_standards
    )
