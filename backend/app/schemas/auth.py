from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="User password")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    role: str
    full_name: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    is_active: bool
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    message: str
