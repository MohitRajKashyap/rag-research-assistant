"""
Conversation Schemas
Request/response models for chat and conversation management.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.models.conversation import MessageRole


class MessageSource(BaseModel):
    """Cited source chunk from RAG retrieval."""
    document_id: str
    document_title: str
    filename: str
    chunk_content: str
    chunk_index: int
    page_number: Optional[int]
    similarity_score: float


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    sources: Optional[List[MessageSource]] = []
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    model_used: Optional[str]
    is_bookmarked: bool
    feedback_rating: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    message_count: int
    total_tokens: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int
    page: int
    page_size: int


class ChatRequest(BaseModel):
    """Single-turn or multi-turn chat request."""
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[uuid.UUID] = None  # None = new conversation
    collection_id: Optional[uuid.UUID] = None     # Limit RAG to a collection
    top_k: int = Field(default=5, ge=1, le=15)
    stream: bool = False


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole = MessageRole.ASSISTANT
    content: str
    sources: List[MessageSource] = []
    tokens_used: int
    latency_ms: int
    model_used: str


class StreamChunk(BaseModel):
    """Single chunk in a streaming response."""
    type: str  # "token" | "sources" | "done" | "error"
    content: Optional[str] = None
    sources: Optional[List[MessageSource]] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None


class MessageFeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    note: Optional[str] = None


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    is_archived: Optional[bool] = None
