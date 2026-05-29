"""
Common response schemas and re-exports.
"""
from typing import Optional, Any, List
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[Any] = None
    code: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    vector_store: str


# Re-exports
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserAdminResponse,
    TokenResponse, LoginRequest, RefreshTokenRequest,
    PasswordChangeRequest, APIKeyResponse,
)
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUpdateRequest,
    DocumentChunkResponse, DocumentSearchRequest, DocumentSearchResponse,
    SearchResult, UploadResponse, BatchUploadResponse,
)
from app.schemas.conversation import (
    MessageResponse, ConversationResponse, ConversationListResponse,
    ChatRequest, ChatResponse, StreamChunk,
    MessageFeedbackRequest, ConversationUpdateRequest, MessageSource,
)

__all__ = [
    "SuccessResponse", "ErrorResponse", "PaginationMeta", "HealthResponse",
    "UserCreate", "UserUpdate", "UserResponse", "UserAdminResponse",
    "TokenResponse", "LoginRequest", "RefreshTokenRequest",
    "PasswordChangeRequest", "APIKeyResponse",
    "DocumentResponse", "DocumentListResponse", "DocumentUpdateRequest",
    "DocumentChunkResponse", "DocumentSearchRequest", "DocumentSearchResponse",
    "SearchResult", "UploadResponse", "BatchUploadResponse",
    "MessageResponse", "ConversationResponse", "ConversationListResponse",
    "ChatRequest", "ChatResponse", "StreamChunk",
    "MessageFeedbackRequest", "ConversationUpdateRequest", "MessageSource",
]
