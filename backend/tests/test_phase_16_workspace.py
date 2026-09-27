import os
import uuid

from app.db.session import SessionLocal
from app.models.project import Project


def login(client, email="officer@cpwd.gov.in", password=os.environ["TEST_DEMO_PASSWORD"]):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def remove_test_project(project_id):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
    finally:
        db.close()


def test_project_create_list_and_duplicate_code(client):
    headers = login(client)
    code = f"UI-{uuid.uuid4().hex[:12]}"
    payload = {"code": code, "title": "Frontend phase project", "description": "Workspace test"}

    created = client.post("/api/v1/projects", json=payload, headers=headers)
    assert created.status_code == 201
    project = created.json()
    assert project["code"] == code
    assert project["document_count"] == 0

    try:
        listed = client.get("/api/v1/projects", headers=headers)
        assert listed.status_code == 200
        assert any(row["id"] == project["id"] for row in listed.json()["projects"])

        duplicate = client.post("/api/v1/projects", json=payload, headers=headers)
        assert duplicate.status_code == 409
    finally:
        remove_test_project(project["id"])


def test_project_and_document_endpoints_enforce_auth_and_permissions(client):
    assert client.get("/api/v1/projects").status_code == 401
    auditor_headers = login(client, "auditor@cag.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    forbidden = client.post(
        "/api/v1/projects",
        json={"code": f"AUD-{uuid.uuid4().hex[:8]}", "title": "Not allowed"},
        headers=auditor_headers,
    )
    assert forbidden.status_code == 403


def test_documents_list_requires_project_access(client):
    headers = login(client)
    code = f"DOC-{uuid.uuid4().hex[:12]}"
    created = client.post(
        "/api/v1/projects",
        json={"code": code, "title": "Document list project"},
        headers=headers,
    )
    assert created.status_code == 201

    project_id = created.json()["id"]
    try:
        documents = client.get(
            f"/api/v1/documents?project_id={project_id}",
            headers=headers,
        )
        assert documents.status_code == 200
        assert documents.json() == []
    finally:
        remove_test_project(project_id)


def test_audit_is_read_only_and_role_restricted(client):
    officer_headers = login(client)
    assert client.get("/api/v1/audit", headers=officer_headers).status_code == 403

    auditor_headers = login(client, "auditor@cag.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    events = client.get("/api/v1/audit?limit=5", headers=auditor_headers)
    assert events.status_code == 200
    assert "events" in events.json()
    assert client.post("/api/v1/audit", headers=auditor_headers).status_code == 405
