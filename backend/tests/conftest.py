import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to sys.path so app can be imported directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import clear_revoked_tokens

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
