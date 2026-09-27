import json
from html import escape
from io import BytesIO
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_client_ip, require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.document import Document
from app.models.recommendation import Recommendation, Evidence
from app.models.review import Review
from app.models.user import User
from app.schemas.project import ProjectCreate
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

router = APIRouter(prefix="/projects", tags=["Projects"])


def _visible_projects(db: Session, user: User):
    query = db.query(Project).filter(Project.is_deleted.is_(False))
    if not user.role or user.role.name != "admin":
        scope = [Project.created_by_id == user.id]
        if user.department_id:
            scope.append(Project.department_id == user.department_id)
        query = query.filter(or_(*scope))
    return query


def _serialize(project: Project) -> dict:
    return {
        "id": project.id,
        "code": project.code,
        "title": project.title,
        "description": project.description,
        "status": project.status,
        "department_id": project.department_id,
        "created_by_id": project.created_by_id,
        "created_at": project.created_at,
        "document_count": len(project.documents),
    }


@router.get("")
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read")),
):
    query = _visible_projects(db, current_user)
    total = query.count()
    projects = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "projects": [_serialize(project) for project in projects]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:write")),
):
    code = payload.code.strip()
    existing = db.query(Project).filter(Project.code.ilike(code), Project.is_deleted.is_(False)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A project with this code already exists")

    project = Project(
        code=code,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        department_id=current_user.department_id,
        created_by_id=current_user.id,
    )
    db.add(project)
    db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        ip_address=get_client_ip(request),
        details=json.dumps({"code": project.code, "title": project.title}),
    ))
    db.commit()
    db.refresh(project)
    return _serialize(project)


@router.get("/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read")),
):
    project = _visible_projects(db, current_user).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _serialize(project)


@router.get("/{project_id}/report.pdf")
def export_project_report(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("project:read")),
):
    project = _visible_projects(db, current_user).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    records = (
        db.query(Recommendation)
        .filter(Recommendation.project_id == project.id, Recommendation.is_deleted.is_(False))
        .options(
            joinedload(Recommendation.standard), joinedload(Recommendation.version),
            joinedload(Recommendation.evidence_items).joinedload(Evidence.document),
            joinedload(Recommendation.reviews).joinedload(Review.reviewer),
        )
        .order_by(Recommendation.created_at.asc())
        .all()
    )
    active_document_count = db.query(Document).filter(
        Document.project_id == project.id,
        Document.is_deleted.is_(False),
    ).count()
    styles = getSampleStyleSheet()
    body, heading = styles["BodyText"], styles["Heading2"]
    body.leading = 14
    parts = [Paragraph("IS Platform — Project Review Report", styles["Title"]), Spacer(1, 5 * mm)]
    parts.append(Paragraph(f"<b>Project:</b> {escape(project.code)} — {escape(project.title)}", body))
    parts.append(Paragraph(f"<b>Status:</b> {escape(project.status)} &nbsp; <b>Exported:</b> {escape(str(project.updated_at or project.created_at))}", body))
    parts.append(Paragraph(f"<b>Documents:</b> {active_document_count} &nbsp; <b>Recommendations:</b> {len(records)}", body))
    parts.append(Spacer(1, 5 * mm))
    parts.append(Paragraph("Review notice", heading))
    parts.append(Paragraph("Search relevance and catalogue metadata do not prove compliance. This report does not approve a tender. Review the complete current licensed standard, source documents, applicable orders, and evidence before making a procurement decision.", body))
    for index, record in enumerate(records, start=1):
        standard = record.standard
        title = f"{index}. {standard.standard_code if standard else 'Standard unavailable'} — {standard.title if standard else ''}"
        block = [Paragraph(escape(title), heading)]
        rows = [
            ["Version", record.version.version_label if record.version else "Not recorded"],
            ["Status", record.status],
            ["Match relevance", f"{record.match_score:.4f} ({record.confidence_level})"],
            ["Certification catalogue check", record.certification_status],
        ]
        table = Table([[Paragraph(f"<b>{escape(str(k))}</b>", body), Paragraph(escape(str(v)), body)] for k, v in rows], colWidths=[48 * mm, 120 * mm])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        block.extend([table, Spacer(1, 3 * mm), Paragraph("<b>Rationale:</b> " + escape(record.why_justification), body)])
        if record.relationship_summary:
            block.append(Paragraph("<b>Relationships:</b> " + escape(record.relationship_summary), body))
        if record.limitations:
            block.append(Paragraph("<b>Limitations:</b> " + escape(record.limitations), body))
        for evidence in record.evidence_items:
            source = evidence.document.filename if evidence.document else (standard.standard_code if standard else "Catalogue")
            block.append(Paragraph(f"<b>Evidence ({escape(evidence.evidence_type)}; {escape(source)}):</b> " + escape(evidence.source_text_snippet), body))
        for review in sorted(record.reviews, key=lambda row: row.created_at or row.id):
            reviewer = review.reviewer.full_name if review.reviewer else "Former user"
            line = f"{review.created_at} — {reviewer}: {review.action}"
            if review.comments:
                line += f" — {review.comments}"
            block.append(Paragraph("<b>Review history:</b> " + escape(line), body))
        parts.append(KeepTogether(block))
        parts.append(Spacer(1, 6 * mm))
    output = BytesIO()
    SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=17 * mm, bottomMargin=17 * mm, title=f"Project report — {project.code}").build(parts)
    output.seek(0)
    safe_code = re.sub(r"[^A-Za-z0-9._-]+", "_", project.code).strip("._-") or "project"
    db.add(AuditLog(
        user_id=current_user.id, action="report.exported", entity_type="project", entity_id=project.id,
        ip_address=get_client_ip(request), user_agent=request.headers.get("User-Agent", "unknown"),
        details=json.dumps({"recommendation_count": len(records), "document_count": active_document_count}),
    ))
    db.commit()
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe_code}-review-report.pdf"'})
