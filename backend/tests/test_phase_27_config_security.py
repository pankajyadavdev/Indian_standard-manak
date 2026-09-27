import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_missing_production_signing_key_is_rejected():
    with pytest.raises(ValidationError, match="SECRET_KEY must be configured"):
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="")


def test_production_signing_key_must_be_long_enough():
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="short")


def test_production_debug_and_wildcard_cors_are_rejected():
    with pytest.raises(ValidationError, match="DEBUG must be disabled"):
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="x" * 32, DEBUG=True)
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(_env_file=None, ENVIRONMENT="test", CORS_ORIGINS=["*"])


def test_nonproduction_missing_key_gets_ephemeral_random_value():
    settings = Settings(_env_file=None, ENVIRONMENT="test", SECRET_KEY="")
    assert len(settings.SECRET_KEY.encode("utf-8")) >= 32
