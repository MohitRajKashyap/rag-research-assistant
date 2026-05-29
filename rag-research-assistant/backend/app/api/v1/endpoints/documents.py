"""
Document Endpoints
POST   /documents/upload           — Upload one or more files
GET    /documents/                 — List user's documents
GET    /documents/{id}             — Get document detail
PUT    /documents/{id}             — Update document metadata
DELETE /documents/{id}             — Delete document
GET    /documents/{id}/chunks      — List chunks
POST   /documents/search           — Semantic search
GET    /documents/{id}/status      — Poll processing status
"""
import os
import uuid
import hashlib
import aiofiles
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.models.document import DocumentType, DocumentStatus
from app.repositories.document_repository import DocumentRepository
from app.schemas import (
    DocumentResponse, DocumentListResponse, DocumentUpdateRequest,
    DocumentChunkResponse, DocumentSearchRequest, DocumentSearchResponse,
    SearchResult, UploadResponse, BatchUploadResponse, SuccessResponse,
)
from app.workers.tasks import ingest_document_task, delete_document_vectors_task
from app.vectorstore.embeddings import get_embedding_service
from app.vectorstore.store import get_vector_store
import time

router = APIRouter(prefix="/documents", tags=["Documents"])

EXTENSION_TO_TYPE = {
    "pdf": DocumentType.PDF,
    "docx": DocumentType.DOCX,
    "txt": DocumentType.TXT,
    "md": DocumentType.MARKDOWN,
}


def _get_doc_type(filename: str) -> DocumentType:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in EXTENSION_TO_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )
    return EXTENSION_TO_TYPE[ext]


async def _save_upload(file: UploadFile, owner_id: str) -> tuple[str, str, int, str]:
    """Save uploaded file to disk. Returns (saved_path, unique_filename, size, hash)."""
    upload_dir = Path(settings.UPLOAD_DIR) / owner_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{file.filename}"
    save_path = upload_dir / unique_name

    sha256 = hashlib.sha256()
    total_size = 0

    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await file.read(65536):
            if total_size + len(chunk) > settings.max_file_size_bytes:
                await f.close()
                os.remove(save_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB",
                )
            sha256.update(chunk)
            await f.write(chunk)
            total_size += len(chunk)

    return str(save_path), unique_name, total_size, sha256.hexdigest()


@router.post("/upload", response_model=BatchUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    files: List[UploadFile] = File(...),
    collection_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more research documents for async ingestion."""
    repo = DocumentRepository(db)
    uploaded = []
    failed = []

    for file in files:
        try:
            if not file.filename:
                failed.append({"filename": "unknown", "error": "Missing filename"})
                continue

            doc_type = _get_doc_type(file.filename)
            file_path, unique_name, file_size, file_hash = await _save_upload(
                file, str(current_user.id)
            )

            # Duplicate detection
            existing = await repo.get_by_hash(file_hash, current_user.id)
            if existing:
                os.remove(file_path)
                failed.append({
                    "filename": file.filename,
                    "error": f"Duplicate document already exists (id={existing.id})",
                })
                continue

            coll_id = uuid.UUID(collection_id) if collection_id else None
            doc = await repo.create(
                owner_id=current_user.id,
                filename=unique_name,
                original_filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                doc_type=doc_type,
                file_hash=file_hash,
                collection_id=coll_id,
                mime_type=file.content_type,
            )

            # Dispatch Celery task
            task = ingest_document_task.delay(
                document_id=str(doc.id),
                file_path=file_path,
                doc_type=doc_type.value,
                owner_id=str(current_user.id),
                collection_id=str(coll_id) if coll_id else None,
            )

            await repo.update_metadata(doc.id, celery_task_id=task.id)
            uploaded.append(UploadResponse(
                document_id=doc.id,
                filename=file.filename,
                status=DocumentStatus.PENDING,
                task_id=task.id,
                message="Document queued for processing",
            ))

        except HTTPException as e:
            failed.append({"filename": getattr(file, "filename", "?"), "error": e.detail})
        except Exception as e:
            failed.append({"filename": getattr(file, "filename", "?"), "error": str(e)})

    return BatchUploadResponse(
        uploaded=uploaded,
        failed=failed,
        total_uploaded=len(uploaded),
        total_failed=len(failed),
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    collection_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's uploaded documents with pagination."""
    repo = DocumentRepository(db)
    skip = (page - 1) * page_size

    status_filter = DocumentStatus(status) if status else None
    coll_id = uuid.UUID(collection_id) if collection_id else None

    docs, total = await repo.list_by_owner(
        owner_id=current_user.id,
        skip=skip,
        limit=page_size,
        status=status_filter,
        collection_id=coll_id,
    )
    total_pages = (total + page_size - 1) // page_size
    return DocumentListResponse(
        documents=docs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single document by ID."""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_and_owner(document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll ingestion status for a document."""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_and_owner(document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    task_info = None
    if doc.celery_task_id:
        from celery.result import AsyncResult
        from app.workers.tasks import celery_app
        result = AsyncResult(doc.celery_task_id, app=celery_app)
        task_info = {"task_id": doc.celery_task_id, "state": result.state}

    return {
        "document_id": str(doc.id),
        "status": doc.status.value,
        "chunk_count": doc.chunk_count,
        "is_indexed": doc.is_indexed,
        "error": doc.processing_error,
        "task": task_info,
    }


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update document title, description, or collection."""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_and_owner(document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await repo.update_metadata(
        document_id,
        **{k: v for k, v in payload.model_dump().items() if v is not None},
    )
    return await repo.get_by_id(document_id)


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its vectors."""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_and_owner(document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get vector IDs to delete from vector store
    chunks = await repo.get_chunks_by_doc(document_id)
    vector_ids = [c.vector_id for c in chunks if c.vector_id]

    # Delete file from disk
    try:
        import os
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass

    await repo.delete(doc)

    # Async vector cleanup
    if vector_ids:
        delete_document_vectors_task.delay(vector_ids)

    return SuccessResponse(message="Document deleted successfully")


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    payload: DocumentSearchRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Perform semantic search across indexed documents."""
    start = time.time()
    embedding_svc = get_embedding_service()
    vector_store = get_vector_store()

    query_embedding = await embedding_svc.embed_text(payload.query)

    filter_meta = {"owner_id": str(current_user.id)}
    if payload.collection_id:
        filter_meta["collection_id"] = str(payload.collection_id)

    raw_results = await vector_store.similarity_search(
        query_embedding=query_embedding,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        filter_metadata=filter_meta,
    )

    results = [
        SearchResult(
            document_id=uuid.UUID(r["metadata"].get("document_id", str(uuid.uuid4()))),
            document_title=r["metadata"].get("document_title", "Unknown"),
            chunk_content=r["text"][:500],
            chunk_index=int(r["metadata"].get("chunk_index", 0)),
            page_number=int(r["metadata"].get("page_number", 0)) or None,
            similarity_score=round(r["score"], 4),
            filename=r["metadata"].get("filename", ""),
        )
        for r in raw_results
    ]

    latency_ms = int((time.time() - start) * 1000)
    return DocumentSearchResponse(
        query=payload.query,
        results=results,
        total_results=len(results),
        search_latency_ms=latency_ms,
    )


@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all text chunks for a document."""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_and_owner(document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = await repo.get_chunks_by_doc(document_id)
    return chunks
