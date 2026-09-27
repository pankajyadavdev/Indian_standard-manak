import pytest
from fastapi.testclient import TestClient
import sys
import os
import secrets

os.environ.setdefault("TEST_DEMO_PASSWORD", secrets.token_urlsafe(32))

# Add backend directory to sys.path so app can be imported directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import clear_revoked_tokens

def pytest_sessionstart(session):
    import app.models  # noqa: F401 - imports model modules so SQLAlchemy metadata is complete
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.db.seed import seed_database
    from app.db.seed_relationships import seed_extended_relationships
    from app.models.user import Role

    if os.environ.get("ENVIRONMENT", "development").lower() != "test":
        raise RuntimeError("Set ENVIRONMENT=test and use a disposable DATABASE_URL before running pytest")
    Base.metadata.create_all(bind=engine)
    database = SessionLocal()
    try:
        is_seeded = database.query(Role).first() is not None
    finally:
        database.close()
    if not is_seeded:
        seed_database(include_demo_users=True, demo_password=os.environ["TEST_DEMO_PASSWORD"])
        seed_extended_relationships()

@pytest.fixture(autouse=True)
def reset_rate_limits():
    RateLimitMiddleware.reset()
    clear_revoked_tokens()
    yield
    RateLimitMiddleware.reset()
    clear_revoked_tokens()

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
