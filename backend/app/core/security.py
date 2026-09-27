from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid
import bcrypt
import jwt
from jwt import InvalidTokenError as JWTError
from app.core.config import settings

# In-memory token blacklist for revoked tokens during logout
revoked_tokens = set()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt work factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(
    subject: str,
    email: str,
    role: str,
    permissions: list[str],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token with unique JTI."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "permissions": permissions,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT refresh token with unique JTI."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token, raising exceptions for invalid or expired tokens."""
    if token in revoked_tokens:
        raise JWTError("Token has been revoked")
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def revoke_token(token: str) -> None:
    """Revoke a token so it cannot be used again."""
    revoked_tokens.add(token)

def clear_revoked_tokens() -> None:
    """Clear revoked tokens registry (used in test isolation)."""
    revoked_tokens.clear()
