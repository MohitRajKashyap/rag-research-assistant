"""
Authentication Endpoints
POST /auth/signup    — Register new user
POST /auth/login     — Obtain JWT tokens
POST /auth/refresh   — Refresh access token
POST /auth/logout    — Invalidate refresh token
GET  /auth/me        — Get current user profile
PUT  /auth/me        — Update profile
POST /auth/change-password
POST /auth/api-key   — Generate API key
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    get_token_subject, validate_password_strength,
)
from app.middleware.auth import get_current_active_user
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas import (
    UserCreate, UserResponse, TokenResponse, LoginRequest,
    RefreshTokenRequest, PasswordChangeRequest, APIKeyResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    repo = UserRepository(db)

    if await repo.email_exists(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await repo.username_exists(payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = await repo.create(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT access + refresh tokens."""
    repo = UserRepository(db)
    user = await repo.get_by_email(payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Update last login
    await repo.update(user, last_login_at=datetime.now(timezone.utc))

    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"role": user.role.value, "email": user.email},
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    from app.core.config import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for new access + refresh tokens."""
    import uuid
    user_id_str = get_token_subject(payload.refresh_token, expected_type="refresh")
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id_str))

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"role": user.role.value, "email": user.email},
    )
    new_refresh = create_refresh_token(subject=str(user.id))

    from app.core.config import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update authenticated user's profile (full_name only for now)."""
    repo = UserRepository(db)
    allowed = {k: v for k, v in payload.items() if k in ("full_name",)}
    user = await repo.update(current_user, **allowed)
    return user


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    repo = UserRepository(db)
    await repo.update_password(current_user, payload.new_password)
    return SuccessResponse(message="Password updated successfully")


@router.post("/api-key", response_model=APIKeyResponse)
async def generate_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for programmatic access."""
    repo = UserRepository(db)
    key = await repo.generate_api_key(current_user)
    return APIKeyResponse(api_key=key)
