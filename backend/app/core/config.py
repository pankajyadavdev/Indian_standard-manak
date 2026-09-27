from typing import List, Union
from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os
import secrets

class Settings(BaseSettings):
    PROJECT_NAME: str = "IS Compliance & Verification Platform"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/is_platform.db"
    
    # Security
    SECRET_KEY: str = "" # Injected via environment variable / .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000"
    ]
    
    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str | None, info: ValidationInfo) -> str:
        environment = str(info.data.get("ENVIRONMENT", "development")).lower()
        if not v:
            if environment == "production":
                raise ValueError("SECRET_KEY must be configured in production")
            return secrets.token_urlsafe(48)
        secret = str(v)
        if environment == "production" and len(secret.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 bytes in production")
        return secret

    @field_validator("DEBUG")
    @classmethod
    def disable_debug_in_production(cls, value: bool, info: ValidationInfo) -> bool:
        if str(info.data.get("ENVIRONMENT", "")).lower() == "production" and value:
            raise ValueError("DEBUG must be disabled in production")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                return json.loads(v)
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def require_explicit_cors_origins(cls, origins: List[str]) -> List[str]:
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not permitted")
        return origins

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    
    # Storage
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    
    # AI Engine
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_MODEL_REVISION: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    RAG_CONFIDENCE_THRESHOLD: float = 0.65
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
