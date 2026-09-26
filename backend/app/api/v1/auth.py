from datetime import datetime, timedelta, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError
from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token
)
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    UserResponse,
    MessageResponse
)
from app.api.deps import get_current_user, require_roles, get_client_ip, security_scheme

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])

@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user with email and password, handling lockout protection and JWT issuance."""
    now = datetime.now(timezone.utc)
    ip_addr = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")

    user = db.query(User).filter(User.email == login_data.email.lower(), User.is_deleted == False).first()
    if not user:
        # Prevent user enumeration with constant-time check
        verify_password("dummy", "$2b$12$e8XG2K7h1mC/sP9iYFsm5eLzL5lQhHwS9pPj8u8O5p9M4E5gC0a8S")
        db.add(AuditLog(
            action="auth.login_failed_unknown_user",
            entity_type="user",
            ip_address=ip_addr,
            user_agent=user_agent,
            details=json.dumps({"email": login_data.email})
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account lockout
    if user.is_locked:
        user_locked_until = user.locked_until
        if user_locked_until and user_locked_until.tzinfo is None:
            user_locked_until = user_locked_until.replace(tzinfo=timezone.utc)
            
        if user_locked_until and now < user_locked_until:
            remaining_mins = max(1, int((user_locked_until - now).total_seconds() / 60) + 1)
            db.add(AuditLog(
                user_id=user.id,
                action="auth.login_blocked_locked_account",
                entity_type="user",
                ip_address=ip_addr,
                user_agent=user_agent,
                details=json.dumps({"email": user.email, "remaining_minutes": remaining_mins})
            ))
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked due to multiple failed login attempts. Try again in {remaining_mins} minutes."
            )
        else:
            # Auto-unlock on expiry
            user.is_locked = False
            user.locked_until = None
            user.failed_login_attempts = 0

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact an administrator."
        )

    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        user.failed_login_attempts += 1
        audit_action = "auth.login_failed"
        
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.is_locked = True
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            audit_action = "auth.account_locked"
            error_detail = f"Invalid credentials. Account locked for {settings.LOCKOUT_MINUTES} minutes."
        else:
            remaining_attempts = settings.MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            error_detail = f"Invalid email or password. {remaining_attempts} attempts remaining."

        db.add(AuditLog(
            user_id=user.id,
            action=audit_action,
            entity_type="user",
            ip_address=ip_addr,
            user_agent=user_agent,
            details=json.dumps({"email": user.email, "failed_attempts": user.failed_login_attempts})
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login: reset failed counters
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None

    role_name = user.role.name if user.role else "viewer"
    permissions = [p.name for p in user.role.permissions] if user.role else []
    
    access_token = create_access_token(
        subject=user.id,
        email=user.email,
        role=role_name,
        permissions=permissions
    )
    refresh_token = create_refresh_token(subject=user.id)

    db.add(AuditLog(
        user_id=user.id,
        action="auth.login_success",
        entity_type="user",
        ip_address=ip_addr,
        user_agent=user_agent,
        details=json.dumps({"email": user.email, "role": role_name})
    ))
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        role=role_name,
        full_name=user.full_name
    )

@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Exchange a valid refresh token for a newly issued access token."""
    ip_addr = get_client_ip(request)
    try:
        payload = decode_token(refresh_data.refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provided token is not a refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user or not user.is_active or user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or locked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role_name = user.role.name if user.role else "viewer"
    permissions = [p.name for p in user.role.permissions] if user.role else []
    
    new_access_token = create_access_token(
        subject=user.id,
        email=user.email,
        role=role_name,
        permissions=permissions
    )

    db.add(AuditLog(
        user_id=user.id,
        action="auth.token_refreshed",
        entity_type="user",
        ip_address=ip_addr,
        details=json.dumps({"email": user.email})
    ))
    db.commit()

    return TokenRefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke the current access token and register audit log."""
    if credentials:
        revoke_token(credentials.credentials)

    db.add(AuditLog(
        user_id=current_user.id,
        action="auth.logout",
        entity_type="user",
        ip_address=get_client_ip(request),
        details=json.dumps({"email": current_user.email})
    ))
    db.commit()

    return MessageResponse(message="Successfully logged out")

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile and active permissions."""
    permissions = [p.name for p in current_user.role.permissions] if current_user.role else []
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.name if current_user.role else "viewer",
        department=current_user.department.name if current_user.department else None,
        is_active=current_user.is_active,
        permissions=permissions
    )

@router.get("/admin-only", response_model=MessageResponse)
def admin_only_endpoint(admin_user: User = Depends(require_roles(["admin"]))):
    """Restricted endpoint demonstrating role-based access enforcement."""
    return MessageResponse(message=f"Welcome Admin: {admin_user.full_name}")
