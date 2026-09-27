import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_client_ip, require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.project import Project
from app.models.recommendation import Evidence, Recommendation
from app.models.review import Review
from app.models.standard import Standard, StandardVersion
from app.models.user import User
from app.schemas.review import RecommendationCreateRequest, ReviewActionRequest
from app.services.certification_engine import certification_engine
from app.services.relationship_engine import relationship_engine
from app.services.search_service import search_engine

router = APIRouter(prefix="/reviews", tags=["Human Review"])
FINAL_STATUSES = {"accepted", "rejected"}
STATUS_FOR_ACTION = {
    "accept": "accepted",
    "reject": "rejected",
    "flag": "flagged",
    "request_review": "review_requested",
}
RECOMMENDATION_LIMITATIONS = (
    "Retrieval score measures text relevance and is not proof of compliance. "
    "The catalogue scope is not the full licensed BIS standard. A qualified reviewer "
    "must verify the tender requirement, current standard text/version, and applicable orders."
)


def _recommendation_query(db: Session, user: User):
    query = (
        db.query(Recommendation)
        .join(Project, Recommendation.project_id == Project.id)
        .filter(Recommendation.is_deleted.is_(False), Project.is_deleted.is_(False))
    )
    if not user.role or user.role.name != "admin":
        scope = [Project.created_by_id == user.id]
        if user.department_id:
            scope.append(Project.department_id == user.department_id)
        query = query.filter(or_(*scope))
    return query


def _serialize_recommendation(item: Recommendation) -> dict:
    evidence = sorted(item.evidence_items, key=lambda row: row.created_at or row.id)
    reviews = sorted(item.reviews, key=lambda row: row.created_at or row.id, reverse=True)
    return {
        "id": item.id,
        "project_id": item.project_id,
        "project_code": item.project.code if item.project else None,
        "project_title": item.project.title if item.project else None,
        "standard_id": item.standard_id,
        "standard_code": item.standard.standard_code if item.standard else None,
        "standard_title": item.standard.title if item.standard else None,
        "standard_category": item.standard.category if item.standard else None,
        "version": item.version.version_label if item.version else None,
        "match_score": item.match_score,
        "confidence_level": item.confidence_level,
        "why_justification": item.why_justification,
        "relationship_summary": item.relationship_summary,
        "limitations": item.limitations,
        "certification_status": item.certification_status,
        "status": item.status,
        "evidence": [
            {
                "id": row.id,
                "source_text_snippet": row.source_text_snippet,
                "page_number": row.page_number,
                "clause_number": row.clause_number,
                "confidence_score": row.confidence_score,
                "evidence_type": row.evidence_type,
                "standard_code": row.standard.standard_code if row.standard else None,
                "document_name": row.document.filename if row.document else None,
            }
            for row in evidence
        ],
        "review_history": [
            {
                "id": row.id,
                "action": row.action,
                "comments": row.comments,
                "reason_code": row.reason_code,
                "reviewer_name": row.reviewer.full_name if row.reviewer else "Former user",
                "created_at": row.created_at,
            }
            for row in reviews
        ],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/recommendations")
def list_review_queue(
    project_id: Optional[str] = None,
    recommendation_status: Optional[str] = Query(None, alias="status", max_length=50),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("review:submit")),
):
    query = _recommendation_query(db, current_user)
    if project_id:
        query = query.filter(Recommendation.project_id == project_id)
    if recommendation_status:
        allowed_statuses = {"pending_review", "review_requested", "flagged", "accepted", "rejected"}
        if recommendation_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Unsupported recommendation status")
        query = query.filter(Recommendation.status == recommendation_status)

    total = query.count()
    rows = (
        query.options(
            joinedload(Recommendation.project),
            joinedload(Recommendation.standard),
            joinedload(Recommendation.version),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.standard),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.document),
            joinedload(Recommendation.reviews).joinedload(Review.reviewer),
        )
        .order_by(Recommendation.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"total": total, "recommendations": [_serialize_recommendation(row) for row in rows]}


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
def create_recommendation(
    payload: RecommendationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analysis:run")),
):
    project = _recommendation_project_query(db, current_user).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    document = db.query(Document).filter(
        Document.id == payload.document_id,
        Document.project_id == project.id,
        Document.is_deleted.is_(False),
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found in this project")
    if document.processing_status != "completed" or not (document.extracted_text or "").strip():
        raise HTTPException(status_code=409, detail="Document processing must complete before creating a recommendation")
    if not document.extracted_text.startswith(payload.source_excerpt):
        raise HTTPException(status_code=422, detail="The search excerpt must match the beginning of the selected document")

    candidates = search_engine.hybrid_search(db, payload.source_excerpt, top_k=20, min_score=0.35)
    match = next((candidate for candidate in candidates if candidate.standard.id == payload.standard_id), None)
    if not match:
        raise HTTPException(status_code=422, detail="The selected standard is not among the server-retrieved candidates")
    standard = db.query(Standard).filter(
        Standard.id == payload.standard_id,
        Standard.is_deleted.is_(False),
        Standard.status == "active",
    ).first()
    if not standard:
        raise HTTPException(status_code=409, detail="Selected standard is not active in the catalogue")
    version = db.query(StandardVersion).filter(
        StandardVersion.standard_id == standard.id,
        StandardVersion.is_current.is_(True),
    ).order_by(StandardVersion.year.desc()).first()
    if not version:
        raise HTTPException(status_code=409, detail="Selected standard has no current catalogue version")

    score = max(0.0, min(float(match.score), 1.0))
    confidence = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
    snippet = " ".join(document.extracted_text.split())[:1200]
    relationships = relationship_engine.get_relationships(db, standard.standard_code)
    relationship_summary = "; ".join(
        f"{item.relationship_type}: {item.target_code} — {item.target_title}"
        for item in relationships[:8]
    ) or "No linked standards relationships are recorded in the catalogue."
    certification = certification_engine.check_certification(db, standard.standard_code, snippet).to_dict()
    why = (
        f"Retrieved from the document using {match.match_type} search (score {score:.4f}). "
        f"Catalogue scope: {standard.scope or 'No scope description is recorded.'} "
        f"Retrieval explanation: {match.explanation}"
    )
    recommendation = Recommendation(
        project_id=project.id,
        standard_id=standard.id,
        version_id=version.id,
        match_score=score,
        confidence_level=confidence,
        why_justification=why,
        relationship_summary=relationship_summary,
        limitations=RECOMMENDATION_LIMITATIONS,
        certification_status=certification["compliance_status"],
        status="pending_review",
    )
    db.add(recommendation)
    db.flush()
    db.add(Evidence(
        recommendation_id=recommendation.id,
        document_id=document.id,
        standard_id=None,
        source_text_snippet=snippet,
        confidence_score=score,
        evidence_type="tender_requirement",
    ))
    db.add(Evidence(
        recommendation_id=recommendation.id,
        document_id=None,
        standard_id=standard.id,
        source_text_snippet=(standard.scope or f"Catalogue entry: {standard.standard_code} — {standard.title}")[:1200],
        confidence_score=score,
        evidence_type="standard_catalog_scope",
    ))
    db.add(AuditLog(
        user_id=current_user.id,
        action="recommendation.created",
        entity_type="recommendation",
        entity_id=recommendation.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "unknown"),
        details=json.dumps({"project_id": project.id, "document_id": document.id, "standard_id": standard.id, "match_score": score}),
    ))
    db.commit()
    recommendation = (
        db.query(Recommendation)
        .options(
            joinedload(Recommendation.project), joinedload(Recommendation.standard),
            joinedload(Recommendation.version), joinedload(Recommendation.evidence_items).joinedload(Evidence.standard),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.document),
            joinedload(Recommendation.reviews).joinedload(Review.reviewer),
        )
        .filter(Recommendation.id == recommendation.id)
        .one()
    )
    return _serialize_recommendation(recommendation)


def _recommendation_project_query(db: Session, user: User):
    query = db.query(Project).filter(Project.is_deleted.is_(False))
    if not user.role or user.role.name != "admin":
        scope = [Project.created_by_id == user.id]
        if user.department_id:
            scope.append(Project.department_id == user.department_id)
        query = query.filter(or_(*scope))
    return query


@router.post("/recommendations/{recommendation_id}/actions")
def record_review_action(
    recommendation_id: str,
    payload: ReviewActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("review:submit")),
):
    recommendation = (
        _recommendation_query(db, current_user)
        .options(
            joinedload(Recommendation.project),
            joinedload(Recommendation.standard),
            joinedload(Recommendation.version),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.standard),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.document),
            joinedload(Recommendation.reviews).joinedload(Review.reviewer),
        )
        .filter(Recommendation.id == recommendation_id)
        .first()
    )
    if not recommendation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    if payload.action in {"accept", "reject"}:
        permissions = {permission.name for permission in current_user.role.permissions} if current_user.role else set()
        if "review:approve" not in permissions and "admin:all" not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accept or reject requires review:approve")
        if recommendation.status in FINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This recommendation already has a final review decision")

    if payload.action in {"reject", "flag", "comment", "request_review"} and not payload.comments:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A comment is required for this review action")

    if payload.action == "accept" and not recommendation.evidence_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A recommendation without linked evidence cannot be accepted",
        )

    previous_status = recommendation.status
    if payload.action in STATUS_FOR_ACTION:
        recommendation.status = STATUS_FOR_ACTION[payload.action]

    review = Review(
        recommendation_id=recommendation.id,
        reviewer_id=current_user.id,
        action=payload.action,
        comments=payload.comments,
        reason_code=payload.reason_code,
    )
    db.add(review)
    db.add(AuditLog(
        user_id=current_user.id,
        action="review.decision",
        entity_type="recommendation",
        entity_id=recommendation.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", "unknown"),
        details=json.dumps({
            "action": payload.action,
            "previous_status": previous_status,
            "new_status": recommendation.status,
            "reason_code": payload.reason_code,
        }),
    ))
    db.commit()
    db.refresh(recommendation)
    return _serialize_recommendation(recommendation)
