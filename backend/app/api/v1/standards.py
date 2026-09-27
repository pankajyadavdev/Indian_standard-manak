from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.standard import Standard, StandardVersion, Amendment, StandardReference
from app.models.certification import Certification
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.search_service import search_engine, calculate_ir_metrics
from app.services.relationship_engine import relationship_engine
from app.services.version_engine import version_engine

router = APIRouter(prefix="/standards", tags=["Standards & Search Engine"])

@router.get("/{standard_code}/relationships")
def get_standard_relationships(
    standard_code: str,
    relationship_type: Optional[str] = None,
    graph: bool = False,
    db: Session = Depends(get_db)
):
    """
    Retrieve relationships for a given standard code.
    Relationship types: normative, test_method, safety, installation, terminology, material, related.
    If graph=True, returns full directed graph nodes and edges.
    """
    if graph:
        return relationship_engine.get_relationship_graph(db, standard_code)
    
    rels = relationship_engine.get_relationships(db, standard_code, rel_type=relationship_type)
    return {
        "standard_code": standard_code,
        "total_relationships": len(rels),
        "relationships": [r.to_dict() for r in rels]
    }

@router.get("/check-version")
def check_standard_version(
    reference: str,
    db: Session = Depends(get_db)
):
    """
    Check if a cited standard reference is current, superseded, or withdrawn.
    Returns amendments, conflict alerts, and recommendation.
    """
    result = version_engine.check_version(db, reference)
    return result.to_dict()

@router.post("/detect-conflicts")
def detect_version_conflicts(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Detect version conflicts within a list of standard references in a tender.
    Identifies contradictory versions, superseded citations, and withdrawn standards.
    """
    references = payload.get("references", [])
    if not references:
        return {"conflicts": [], "total_conflicts": 0}
    conflicts = version_engine.detect_version_conflicts(db, references)
    return {"references": references, "total_conflicts": len(conflicts), "conflicts": conflicts}

@router.get("")
def list_standards(
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List BIS standards with optional category filtering."""
    q = db.query(Standard).filter(Standard.is_deleted == False)
    if category:
        q = q.filter(Standard.category.ilike(f"%{category}%"))
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    
    results = []
    for s in items:
        cur_ver = next((v for v in s.versions if v.is_current), None)
        results.append({
            "id": s.id,
            "standard_code": s.standard_code,
            "title": s.title,
            "category": s.category,
            "status": s.status,
            "current_version": cur_ver.version_label if cur_ver else None,
            "versions_count": len(s.versions),
            "certifications_count": len(s.certifications)
        })
    return {"total": total, "standards": results}

@router.get("/{standard_id}")
def get_standard_details(standard_id: str, db: Session = Depends(get_db)):
    """Retrieve full standard details including versions, amendments, references, and certifications."""
    std = db.query(Standard).filter(Standard.id == standard_id, Standard.is_deleted == False).first()
    if not std:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standard not found")

    versions_data = []
    for v in std.versions:
        amendments = [{
            "id": a.id,
            "amendment_number": a.amendment_number,
            "amendment_code": a.amendment_code,
            "issue_date": a.issue_date,
            "summary": a.summary
        } for a in v.amendments]
        
        versions_data.append({
            "id": v.id,
            "year": v.year,
            "version_label": v.version_label,
            "is_current": v.is_current,
            "effective_date": v.effective_date,
            "changelog": v.changelog,
            "amendments": amendments
        })

    outbound_refs = [{
        "target_standard_code": r.target_standard.standard_code,
        "target_title": r.target_standard.title,
        "relationship_type": r.relationship_type,
        "clause_reference": r.clause_reference,
        "description": r.description
    } for r in std.outbound_references]

    inbound_refs = [{
        "source_standard_code": r.source_standard.standard_code,
        "source_title": r.source_standard.title,
        "relationship_type": r.relationship_type,
        "clause_reference": r.clause_reference,
        "description": r.description
    } for r in std.inbound_references]

    certs = [{
        "id": c.id,
        "certification_type": c.certification_type,
        "is_mandatory": c.is_mandatory,
        "qco_order_number": c.qco_order_number,
        "applicable_ministry": c.applicable_ministry,
        "compliance_category": c.compliance_category,
        "details": c.details
    } for c in std.certifications]

    return {
        "id": std.id,
        "standard_code": std.standard_code,
        "title": std.title,
        "category": std.category,
        "status": std.status,
        "scope": std.scope,
        "bis_url": std.bis_url,
        "versions": versions_data,
        "normative_references": outbound_refs,
        "referenced_by": inbound_refs,
        "certifications": certs
    }

@router.post("/search", response_model=SearchResponse)
def search_standards(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search standards using:
    1. Exact search
    2. Keyword search
    3. Semantic search
    4. Metadata filtering
    5. Hybrid search (RRF fusion)
    6. Reranking and unrelated standard pruning
    """
    stype = req.search_type.lower()
    if stype == "exact":
        results = search_engine.exact_search(db, req.query)
    elif stype == "keyword":
        results = search_engine.keyword_search(db, req.query, req.category_filter)
    elif stype == "semantic":
        results = search_engine.semantic_search(db, req.query, top_k=req.top_k)
    else: # hybrid
        results = search_engine.hybrid_search(
            db,
            req.query,
            category_filter=req.category_filter,
            top_k=req.top_k,
            min_score=req.min_score
        )

    items = [SearchResultItem(**r.to_dict()) for r in results]
    return SearchResponse(
        query=req.query,
        search_type=stype,
        total_results=len(items),
        results=items
    )
