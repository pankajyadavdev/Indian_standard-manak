import pytest

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "IS Compliance" in data["service"]
    assert "version" in data

def test_health_liveness(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"

def test_health_readiness(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["checks"]["database"] is True
    assert data["checks"]["storage"] is True

def test_security_headers(client):
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"

def test_info_endpoint(client):
    response = client.get("/api/v1/health/info")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data
