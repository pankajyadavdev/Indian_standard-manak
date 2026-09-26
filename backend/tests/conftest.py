import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to sys.path so app can be imported directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
