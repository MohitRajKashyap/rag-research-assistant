"""
Security Module
JWT token generation/validation, password hashing, and security utilities.
Production-grade implementation with refresh token support.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import secrets
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token types
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, int],
    additional_claims: Optional[dict] = None,
) -> str:
    """
    Create a short-lived JWT access token.
    
    Args:
        subject: The token subject (typically user ID)
        additional_claims: Extra claims to include in the token
    
    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": ACCESS_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(16),  # Unique token ID for revocation
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: Union[str, int]) -> str:
    """
    Create a long-lived JWT refresh token.
    
    Args:
        subject: The token subject (typically user ID)
    
    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": REFRESH_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT string to decode
    
    Returns:
        Token payload dictionary
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning("JWT decode error", error=str(e))
        raise credentials_exception


def get_token_subject(token: str, expected_type: str = ACCESS_TOKEN_TYPE) -> str:
    """
    Extract and validate subject from a token.
    
    Args:
        token: JWT string
        expected_type: Expected token type ('access' or 'refresh')
    
    Returns:
        Subject string (user ID)
    
    Raises:
        HTTPException: If token type doesn't match
    """
    payload = decode_token(token)
    token_type = payload.get("type")
    subject = payload.get("sub")

    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type. Expected {expected_type}",
        )
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return subject


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"rag_{secrets.token_urlsafe(32)}"


def validate_password_strength(password: str) -> bool:
    """
    Validate password meets security requirements.
    At least 8 chars, 1 uppercase, 1 lowercase, 1 digit.
    """
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_upper and has_lower and has_digit
