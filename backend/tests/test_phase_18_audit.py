import os
import json

from app.db.session import SessionLocal
from app.models.audit import AuditLog


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_standard_search_is_audited_without_storing_query_text(client):
    officer = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    response = client.post(
        "/api/v1/standards/search",
        json={"query": "confidential project specification IS 456", "search_type": "exact"},
        headers=officer,
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        event = db.query(AuditLog).filter(
            AuditLog.action == "search.standards",
            AuditLog.user_id.is_not(None),
        ).order_by(AuditLog.timestamp.desc()).first()
        assert event is not None
        details = json.loads(event.details)
        assert details["query_length"] == len("confidential project specification IS 456")
        assert "query_sha256" in details
        assert "confidential project specification" not in event.details
    finally:
        db.close()


def test_audit_reader_permission_and_read_only_api(client):
    admin = login(client, "admin@is-platform.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    response = client.get("/api/v1/audit?limit=10", headers=admin)
    assert response.status_code == 200
    assert "events" in response.json()

    officer = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    forbidden = client.get("/api/v1/audit", headers=officer)
    assert forbidden.status_code == 403

    deletion = client.delete("/api/v1/audit", headers=admin)
    assert deletion.status_code == 405
