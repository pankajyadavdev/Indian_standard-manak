import os
import time
import uuid
import io
import zipfile

from app.core.rate_limit import RateLimitMiddleware
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.project import Project
from app.models.standard import Standard
from app.models.user import User


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_private_document():
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == "officer@cpwd.gov.in").one()
        project = Project(
            code=f"SEC-{uuid.uuid4().hex[:12]}",
            title="Private document security fixture",
            department_id=owner.department_id,
            created_by_id=owner.id,
        )
        db.add(project)
        db.flush()
        document = Document(
            project_id=project.id,
            filename="private.txt",
            stored_filename="private.txt",
            file_type="txt",
            file_size_bytes=24,
            file_hash_sha256="a" * 64,
            processing_status="completed",
            extracted_text="Confidential fixture content",
            total_pages=1,
        )
        db.add(document)
        db.commit()
        return project.id, document.id
    finally:
        db.close()


def remove_private_document(project_id):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
    finally:
        db.close()


def test_document_idor_is_denied_across_departments(client):
    project_id, document_id = create_private_document()
    try:
        auditor = login(client, "auditor@cag.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        assert client.get(f"/api/v1/documents/{document_id}", headers=auditor).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/chunks", headers=auditor).status_code == 404

        extract = client.post(
            "/api/v1/analysis/extract-specifications",
            headers=auditor,
            json={"document_id": document_id},
        )
        assert extract.status_code == 404
        rag = client.post(
            "/api/v1/analysis/rag-explain",
            headers=auditor,
            json={"query": "confidential fixture content", "document_id": document_id},
        )
        assert rag.status_code == 404
    finally:
        remove_private_document(project_id)


def test_forwarded_header_cannot_bypass_ip_rate_limit(client):
    RateLimitMiddleware.request_records["testclient"] = [time.time()] * 120
    response = client.get(
        "/api/v1/standards",
        headers={"X-Forwarded-For": f"{uuid.uuid4()}, 203.0.113.9"},
    )
    assert response.status_code == 429


def test_search_rejects_malformed_payload_and_sql_injection_is_data(client):
    headers = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    malformed = client.post("/api/v1/standards/search", json={"query": "x", "search_type": "unknown"}, headers=headers)
    assert malformed.status_code == 422
    malformed_json = client.post(
        "/api/v1/standards/search",
        data="{not valid json",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert malformed_json.status_code == 422

    injection = client.post(
        "/api/v1/standards/search",
        json={"query": "' OR 1=1; DROP TABLE standards; --", "search_type": "exact"},
        headers=headers,
    )
    assert injection.status_code == 200
    assert injection.json()["results"] == []
    assert client.post(
        "/api/v1/standards/search",
        json={"query": "IS 4569", "search_type": "exact"},
        headers=headers,
    ).json()["results"] == []
    db = SessionLocal()
    try:
        assert db.query(Standard).count() > 0
    finally:
        db.close()


def test_office_zip_bomb_is_rejected():
    from app.services.document_processor import DocumentValidationError, validate_file_content

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("word/document.xml", b"A" * 300_000)
    try:
        validate_file_content("payload.docx", archive.getvalue())
        raise AssertionError("Expected high-ratio Office archive to be rejected")
    except DocumentValidationError as exc:
        assert "compression ratio" in str(exc)


def test_oversized_upload_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    officer = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    project_response = client.post(
        "/api/v1/projects",
        headers=officer,
        json={"code": f"SIZE-{uuid.uuid4().hex[:10]}", "title": "Upload size fixture"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    try:
        response = client.post(
            "/api/v1/documents/upload",
            headers=officer,
            data={"project_id": project_id},
            files={"file": ("large.txt", b"x" * (1024 * 1024 + 1), "text/plain")},
        )
        assert response.status_code == 413
    finally:
        remove_private_document(project_id)
