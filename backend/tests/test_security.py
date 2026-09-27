
def test_owasp_security_headers_present(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    headers = response.headers
    
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers.get("Permissions-Policy", "")
    assert "X-Request-ID" in headers
    assert "X-Process-Time" in headers

def test_internal_error_stack_trace_sanitization():
    """Ensure that 500 internal server errors mask the stack trace from responses."""
    from fastapi.testclient import TestClient
    from app.main import app
    client_no_raise = TestClient(app, raise_server_exceptions=False)
    response = client_no_raise.get("/api/v1/simulate-error")
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "Internal Server Error"
    assert "Traceback" not in str(data)
    assert "RuntimeError" not in str(data)
    assert "request_id" in data
    assert "An unexpected error occurred" in data["message"]

def test_input_validation_schema_rejection(client):
    """Ensure invalid JSON payloads produce structured 422 responses."""
    response = client.post("/api/v1/auth/login", json={
        "email": "not-an-email",
        "password": "12"  # min_length is 6
    })
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "Validation Error"
    assert "details" in data
    assert len(data["details"]) >= 1

def test_rate_limiting_enforcement(client):
    """Ensure rate limiter triggers 429 when threshold exceeded."""
    # Auth login has limit 20 per minute
    # Let's send 22 requests to /api/v1/auth/login
    hit_rate_limit = False
    for i in range(25):
        resp = client.post("/api/v1/auth/login", json={
            "email": f"test_{i}@unknown.com",
            "password": "Password123!"
        })
        if resp.status_code == 429:
            hit_rate_limit = True
            assert "Rate limit exceeded" in resp.json()["message"]
            assert "Retry-After" in resp.headers
            assert resp.headers["X-RateLimit-Remaining"] == "0"
            break
            
    assert hit_rate_limit is True

def test_cors_headers(client):
    """Test CORS preflight handling."""
    response = client.options("/api/v1/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
