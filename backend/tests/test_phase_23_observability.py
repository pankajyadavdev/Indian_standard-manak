import os
from app.core.rate_limit import RateLimitMiddleware


def login(client, email, password):
    RateLimitMiddleware.reset()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_reports_database_storage_and_embedding_state(client):
    live = client.get("/api/v1/health")
    ready = client.get("/api/v1/health/ready")
    assert live.json()["status"] == "UP"
    assert ready.json()["status"] == "READY"
    assert ready.json()["checks"]["database"] is True
    assert ready.json()["checks"]["storage"] is True
    assert ready.json()["checks"]["embedding_model"] in {"not_loaded", "ready", "lexical_fallback"}


def test_prometheus_metrics_require_auditor_permission_and_record_requests(client):
    admin = login(client, "admin@is-platform.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    health = client.get("/api/v1/health", headers={"X-Request-ID": "metrics-correlation-1"})
    assert health.headers["X-Request-ID"] == "metrics-correlation-1"

    exact_search = client.post(
        "/api/v1/standards/search",
        json={"query": "IS 456", "search_type": "exact"},
        headers=admin,
    )
    assert exact_search.status_code == 200

    metrics = client.get("/api/v1/health/metrics", headers=admin)
    assert metrics.status_code == 200
    assert "is_platform_http_requests_total" in metrics.text
    assert 'route="/api/v1/standards/search"' in metrics.text
    assert 'operation="standards_search"' in metrics.text
    assert "is_platform_ai_operation_duration_seconds" in metrics.text

    officer = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
    forbidden = client.get("/api/v1/health/metrics", headers=officer)
    assert forbidden.status_code == 403


def test_invalid_request_id_is_replaced(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad request id"})
    request_id = response.headers["X-Request-ID"]
    assert request_id != "bad request id"
    assert len(request_id) == 36
