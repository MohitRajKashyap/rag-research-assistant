"""
User Schemas
Pydantic models for request/response validation.
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

    @validator("password")
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    total_queries: int
    total_tokens_used: int
    total_documents_uploaded: int
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserAdminResponse(UserResponse):
    """Extended user info for admin endpoints."""
    api_key: Optional[str]
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @validator("new_password")
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Must contain uppercase")
        if not any(c.islower() for c in v):
            raise ValueError("Must contain lowercase")
        if not any(c.isdigit() for c in v):
            raise ValueError("Must contain digit")
        return v


class APIKeyResponse(BaseModel):
    api_key: str
    message: str = "Store this key safely. It will not be shown again."
