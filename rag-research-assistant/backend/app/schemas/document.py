"""
Document Schemas
Request/response validation for document ingestion and retrieval.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    doc_type: DocumentType
    title: Optional[str]
    description: Optional[str]
    author: Optional[str]
    total_pages: Optional[int]
    total_words: Optional[int]
    status: DocumentStatus
    chunk_count: int
    is_indexed: bool
    collection_id: Optional[uuid.UUID]
    created_at: datetime
    indexed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    collection_id: Optional[uuid.UUID] = None


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int]
    token_count: Optional[int]

    class Config:
        from_attributes = True


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    collection_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    document_id: uuid.UUID
    document_title: str
    chunk_content: str
    chunk_index: int
    page_number: Optional[int]
    similarity_score: float
    filename: str


class DocumentSearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    search_latency_ms: int


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: DocumentStatus
    task_id: str
    message: str


class BatchUploadResponse(BaseModel):
    uploaded: List[UploadResponse]
    failed: List[Dict[str, Any]]
    total_uploaded: int
    total_failed: int
