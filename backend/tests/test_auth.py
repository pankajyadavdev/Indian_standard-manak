import pytest
from datetime import timedelta
from app.core.security import create_access_token, create_refresh_token
from app.db.session import SessionLocal
from app.models.user import User

@pytest.fixture(autouse=True)
def unlock_test_users():
    """Ensure test users are unlocked before each test."""
    yield
    db = SessionLocal()
    users = db.query(User).all()
    for u in users:
        u.is_locked = False
        u.failed_login_attempts = 0
        u.locked_until = None
    db.commit()
    db.close()

def test_valid_login(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "Officer@12345"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "procurement_officer"
    assert data["email"] == "officer@cpwd.gov.in"

def test_invalid_login_wrong_password(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "WrongPassword999!"
    })
    assert response.status_code == 401
    assert "remaining" in response.json()["detail"]

def test_invalid_login_nonexistent_user(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@fake.com",
        "password": "SomePassword123"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_account_lockout(client):
    # Perform 5 consecutive failed logins for auditor
    for i in range(4):
        resp = client.post("/api/v1/auth/login", json={
            "email": "auditor@cag.gov.in",
            "password": "WrongPassword!"
        })
        assert resp.status_code == 401

    # 5th attempt triggers lockout
    resp5 = client.post("/api/v1/auth/login", json={
        "email": "auditor@cag.gov.in",
        "password": "WrongPassword!"
    })
    assert resp5.status_code == 401
    assert "Account locked" in resp5.json()["detail"]

    # 6th attempt while locked should return 403 Forbidden
    resp6 = client.post("/api/v1/auth/login", json={
        "email": "auditor@cag.gov.in",
        "password": "Auditor@12345"  # even with correct password!
    })
    assert resp6.status_code == 403
    assert "Account locked due to multiple failed login attempts" in resp6.json()["detail"]

def test_unauthorized_api_access_missing_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Authentication credentials were not provided" in response.json()["detail"]

def test_expired_token(client):
    # Generate an already expired token (-1 minute)
    expired_token = create_access_token(
        subject="test-id",
        email="test@test.com",
        role="viewer",
        permissions=[],
        expires_delta=timedelta(minutes=-1)
    )
    response = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {expired_token}"
    })
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]

def test_role_violation(client):
    # Login as procurement officer
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "Officer@12345"
    })
    token = login_resp.json()["access_token"]

    # Try to access admin-only endpoint
    resp = client.get("/api/v1/auth/admin-only", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 403
    assert "Access forbidden" in resp.json()["detail"]

def test_admin_access_success(client):
    # Login as admin
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "admin@is-platform.gov.in",
        "password": "Admin@12345"
    })
    admin_token = login_resp.json()["access_token"]

    # Access admin-only endpoint
    resp = client.get("/api/v1/auth/admin-only", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    assert "Welcome Admin" in resp.json()["message"]

def test_token_refresh(client):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "Officer@12345"
    })
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

def test_logout_and_revocation(client):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "Officer@12345"
    })
    token = login_resp.json()["access_token"]

    # Verify token works
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200

    # Token should now be rejected as revoked
    revoked_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked_resp.status_code == 401
    assert "revoked" in revoked_resp.json()["detail"]
