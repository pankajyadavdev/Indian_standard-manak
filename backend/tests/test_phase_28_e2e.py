import os
import uuid
from types import SimpleNamespace

from app.api.v1 import documents as documents_api
from app.api.v1 import reviews as reviews_api
from app.api.v1 import standards as standards_api
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.standard import Standard
from app.services.search_service import SearchResult


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": os.environ["TEST_DEMO_PASSWORD"]})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_document_to_review_and_audited_report_flow(client, monkeypatch, tmp_path):
    """Exercise the procurement flow with controlled retrieval so the test needs no model download."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(documents_api.vector_index, "add_chunks", lambda chunks: None)
    officer = _login(client, "officer@cpwd.gov.in")
    reviewer = _login(client, "reviewer@bis.gov.in")

    created = client.post("/api/v1/projects", headers=officer, json={
        "code": f"E2E-{uuid.uuid4().hex[:10]}",
        "title": "Concrete procurement verification",
        "description": "End-to-end flow fixture",
    })
    assert created.status_code == 201
    project_id = created.json()["id"]
    text = (
        "The concrete works shall comply with IS 456:2000, Plain and Reinforced Concrete Code of Practice. "
        "The contractor shall provide test certificates and ensure concrete strength is verified."
    )
    upload = client.post(
        "/api/v1/documents/upload",
        headers=officer,
        data={"project_id": project_id},
        files={"file": ("tender.txt", text.encode(), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    assert client.get(f"/api/v1/documents/{document_id}", headers=officer).status_code == 200

    extracted = client.post("/api/v1/analysis/extract-specifications", headers=officer, json={"document_id": document_id})
    assert extracted.status_code == 200
    cited = extracted.json()["entities"]["standards_cited"]
    assert any(item.startswith("IS 456") for item in cited)
    assert client.post("/api/v1/analysis/detect-gaps", headers=officer, json={"text": text}).status_code == 200
    assert client.post("/api/v1/analysis/detect-conflicts", headers=officer, json={"text": text, "cited_references": cited}).status_code == 200
    assert client.get("/api/v1/standards/check-version", params={"reference": "IS 456:2000"}, headers=officer).status_code == 200
    assert client.get("/api/v1/standards/IS%20456/relationships", headers=officer).status_code == 200
    assert client.post("/api/v1/analysis/certification-check", headers=officer, json={"standards": ["IS 456"], "tender_clause_text": text}).status_code == 200

    db = SessionLocal()
    try:
        standard = db.query(Standard).filter(Standard.standard_code == "IS 456").one()
        version = next(item for item in standard.versions if item.is_current)
        detached_standard = SimpleNamespace(
            id=standard.id,
            standard_code=standard.standard_code,
            title=standard.title,
            category=standard.category,
            status=standard.status,
            scope=standard.scope,
            versions=[SimpleNamespace(is_current=True, version_label=version.version_label)],
        )
        candidate = SearchResult(detached_standard, 0.82, "controlled-e2e", "Controlled candidate for route integration")
    finally:
        db.close()
    monkeypatch.setattr(reviews_api.search_engine, "hybrid_search", lambda *args, **kwargs: [candidate])
    monkeypatch.setattr(standards_api.search_engine, "hybrid_search", lambda *args, **kwargs: [candidate])
    search = client.post("/api/v1/standards/search", headers=officer, json={"query": text, "search_type": "hybrid"})
    assert search.status_code == 200 and search.json()["results"][0]["standard_code"] == "IS 456"
    rag = client.post("/api/v1/analysis/rag-explain", headers=officer, json={"query": "What concrete standard is identified?", "document_id": document_id})
    assert rag.status_code == 200 and rag.json()["is_verified"]

    forged_excerpt = client.post("/api/v1/reviews/recommendations", headers=officer, json={
        "project_id": project_id, "document_id": document_id, "standard_id": candidate.standard.id,
        "source_excerpt": "Unrelated text supplied by a client.",
    })
    assert forged_excerpt.status_code == 422
    recommendation = client.post("/api/v1/reviews/recommendations", headers=officer, json={
        "project_id": project_id, "document_id": document_id, "standard_id": candidate.standard.id,
        "source_excerpt": text,
    })
    assert recommendation.status_code == 201, recommendation.text
    recommendation_id = recommendation.json()["id"]
    assert recommendation.json()["status"] == "pending_review"
    assert {item["evidence_type"] for item in recommendation.json()["evidence"]} == {"tender_requirement", "standard_catalog_scope"}
    accepted = client.post(
        f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
        headers=reviewer,
        json={"action": "accept", "comments": "Verified for this workflow fixture."},
    )
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"

    report = client.get(f"/api/v1/projects/{project_id}/report.pdf", headers=officer)
    assert report.status_code == 200 and report.headers["content-type"].startswith("application/pdf")
    assert report.content.startswith(b"%PDF")
    db = SessionLocal()
    try:
        actions = {row.action for row in db.query(AuditLog).filter(AuditLog.entity_id.in_([project_id, recommendation_id])).all()}
        assert "recommendation.created" in actions
        assert "review.decision" in actions
        assert "report.exported" in actions
        project = db.query(Project).filter(Project.id == project_id).one()
        db.delete(project)
        db.commit()
    finally:
        db.close()
