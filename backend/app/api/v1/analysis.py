import json
import time
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.standard import Standard
from app.models.audit import AuditLog
from app.api.deps import get_current_user, get_client_ip
from app.core.audit import record_activity
from app.core.access import visible_document_query
from app.core.metrics import record_ai_operation
from app.schemas.search import SearchRequest
from app.services.search_service import search_engine
from app.schemas.specification import SpecificationExtractionRequest, SpecificationExtractionResponse
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.entity_extractor import extract_entities
from app.services.rag_engine import rag_engine
from app.services.certification_engine import certification_engine
from app.services.gap_detector import gap_detector
from app.services.conflict_detector import conflict_detector
from app.services.multilingual import translate_term, get_standard_title_hindi, transliterate_standard_code
from app.services.explainable_ai import explainer

router = APIRouter(prefix="/analysis", tags=["Specification Analysis & Extraction"])

@router.post("/detect-gaps")
def detect_gaps(
    payload: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Detect missing mandatory standards and normative references in a tender."""
    started = time.perf_counter()
    cited = payload.get("cited_standards", [])
    categories = payload.get("categories", [])
    text = payload.get("text", None)
    if text:
        report = gap_detector.detect_gaps_from_text(db, text)
    elif not cited:
        raise HTTPException(status_code=400, detail="'cited_standards' or 'text' required.")
    else:
        report = gap_detector.detect_gaps(db, cited, categories)
    result = report.to_dict()
    record_activity(db, request, current_user, "ai.gap_analysis", "tender_analysis", details={
        "input_type": "text" if text else "cited_standards",
        "input_length": len(text) if text else 0,
        "cited_standard_count": len(cited) if isinstance(cited, list) else 0,
        "category_count": len(categories) if isinstance(categories, list) else 0,
        "gap_count": report.gaps_found,
    })
    db.commit()
    record_ai_operation("gap_analysis", (time.perf_counter() - started) * 1000)
    return result

@router.post("/detect-conflicts")
def detect_conflicts_endpoint(
    payload: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Detect specification conflicts: version, material grade, exposure, and certification contradictions."""
    started = time.perf_counter()
    text = payload.get("text", "")
    references = payload.get("cited_references", [])
    if not text:
        raise HTTPException(status_code=400, detail="'text' field required.")
    report = conflict_detector.detect_conflicts(db, text, references)
    result = report.to_dict()
    record_activity(db, request, current_user, "ai.conflict_analysis", "tender_analysis", details={
        "input_length": len(text),
        "reference_count": len(references) if isinstance(references, list) else 0,
        "conflict_count": report.total_conflicts,
        "critical_conflict_count": report.critical_count,
    })
    db.commit()
    record_ai_operation("conflict_analysis", (time.perf_counter() - started) * 1000)
    return result

@router.get("/translate")
def translate_endpoint(term: str, lang: str = "hi"):
    """Translate IS platform terms to Hindi."""
    return {
        "term": term,
        "language": lang,
        "translation": translate_term(term, lang)
    }

@router.get("/standard-hindi-title")
def get_hindi_title(standard_code: str):
    """Get Hindi title for a BIS standard."""
    hi_title = get_standard_title_hindi(standard_code)
    return {
        "standard_code": standard_code,
        "transliterated_code": transliterate_standard_code(standard_code),
        "hindi_title": hi_title
    }

@router.post("/explain-search")
def explain_search(
    req: SearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explain results retrieved by the server; caller-supplied candidates are never trusted."""
    started = time.perf_counter()
    stype = req.search_type
    if stype == "exact":
        results = search_engine.exact_search(db, req.query)
    elif stype == "keyword":
        results = search_engine.keyword_search(db, req.query, req.category_filter)
    elif stype == "semantic":
        results = search_engine.semantic_search(db, req.query, top_k=req.top_k)
    else:
        results = search_engine.hybrid_search(
            db, req.query, category_filter=req.category_filter, top_k=req.top_k, min_score=req.min_score
        )
    explained = explainer.explain_search_result(req.query, [item.to_dict() for item in results], stype)
    record_activity(
        db, request, current_user, "ai.search_explained", "standards_query",
        details={"search_type": stype, "result_count": len(results), "query_length": len(req.query)},
    )
    db.commit()
    record_ai_operation("search_explanation", (time.perf_counter() - started) * 1000)
    return explained


@router.post("/rag-explain", response_model=RAGQueryResponse)
def rag_explain(
    req: RAGQueryRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evidence-Grounded RAG Endpoint:
    The system can ONLY explain retrieved evidence.
    If evidence is absent, strictly returns 'Insufficient verified evidence.'
    """
    started = time.perf_counter()
    if req.document_id:
        permissions = {permission.name for permission in current_user.role.permissions} if current_user.role else set()
        if "document:read" not in permissions and "admin:all" not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing document:read permission")
        if not visible_document_query(db, current_user).filter(Document.id == req.document_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    rag_res = rag_engine.generate_grounded_explanation(
        db=db,
        query=req.query,
        document_id=req.document_id
    )
    record_activity(db, request, current_user, "ai.rag_analysis", "document" if req.document_id else "query", req.document_id, {
        "query_length": len(req.query),
        "is_verified": rag_res.is_verified,
        "evidence_count": len(rag_res.evidence),
        "recommendation_count": len(rag_res.recommended_standards),
    })
    db.commit()
    record_ai_operation("rag", (time.perf_counter() - started) * 1000)
    return RAGQueryResponse(**rag_res.to_dict())

@router.post("/certification-check")
def certification_check(
    payload: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluate one or more standard codes for certification compliance (QCO/BIS rules).
    Supply optional tender_clause_text to test for explicit ISI mark requirement.
    """
    started = time.perf_counter()
    standards = payload.get("standards", [])
    tender_text = payload.get("tender_clause_text", None)
    if not standards:
        raise HTTPException(status_code=400, detail="'standards' list is required.")
    result = certification_engine.evaluate_tender(db, standards, tender_text)
    record_activity(db, request, current_user, "ai.certification_check", "tender_analysis", details={
        "standard_count": len(standards) if isinstance(standards, list) else 0,
        "clause_text_length": len(tender_text) if isinstance(tender_text, str) else 0,
        "overall_status": result["overall_status"],
    })
    db.commit()
    record_ai_operation("certification", (time.perf_counter() - started) * 1000)
    return result

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
    started = time.perf_counter()
    ip_addr = get_client_ip(request)
    text_to_analyze = ""

    if req.document_id:
        permissions = {permission.name for permission in current_user.role.permissions} if current_user.role else set()
        if "document:read" not in permissions and "admin:all" not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing document:read permission")
        doc = visible_document_query(db, current_user).filter(Document.id == req.document_id).first()
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
    record_ai_operation("specification_extraction", (time.perf_counter() - started) * 1000)

    return SpecificationExtractionResponse(
        document_id=req.document_id,
        entities=entities,
        total_entities_found=total_entities,
        standards_matched_count=matched_standards
    )
