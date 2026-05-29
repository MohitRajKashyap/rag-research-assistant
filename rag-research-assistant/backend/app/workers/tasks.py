"""
Celery Workers
Background task processing for document ingestion.
Uses Redis as broker and result backend.
"""
import asyncio
import uuid
from typing import Optional
from celery import Celery
from celery.utils.log import get_task_logger

from app.core.config import settings

logger = get_task_logger(__name__)

# -------------------------------------------------------
# Celery app setup
# -------------------------------------------------------
celery_app = Celery(
    "rag_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,                    # Ack after task completes (safer)
    worker_prefetch_multiplier=1,           # One task per worker at a time
    task_soft_time_limit=300,               # 5 min soft limit
    task_time_limit=600,                    # 10 min hard limit
    result_expires=86400,                   # Results kept for 24 hours
    beat_schedule={},                       # No periodic tasks by default
)


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# -------------------------------------------------------
# Tasks
# -------------------------------------------------------
@celery_app.task(
    bind=True,
    name="workers.ingest_document",
    max_retries=3,
    default_retry_delay=30,
)
def ingest_document_task(
    self,
    document_id: str,
    file_path: str,
    doc_type: str,
    owner_id: str,
    collection_id: Optional[str] = None,
):
    """
    Background task: parse a document, generate embeddings, and index it.

    Steps:
      1. Update document status → PROCESSING
      2. Parse file and extract text chunks
      3. Generate embeddings for each chunk
      4. Store embeddings in vector store
      5. Save chunks to PostgreSQL
      6. Update document status → INDEXED
    """
    logger.info(f"Starting ingestion for document {document_id}")

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.document import DocumentStatus, DocumentChunk
        from app.repositories.document_repository import DocumentRepository
        from app.repositories.user_repository import UserRepository
        from app.rag.document_processor import DocumentProcessor
        from app.vectorstore.embeddings import EmbeddingService
        from app.vectorstore.store import get_vector_store
        import uuid as _uuid

        engine = create_async_engine(settings.DATABASE_URL, pool_size=2)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async with SessionLocal() as db:
            doc_repo = DocumentRepository(db)
            user_repo = UserRepository(db)
            doc_id = _uuid.UUID(document_id)

            try:
                # Step 1: Mark as processing
                await doc_repo.update_status(doc_id, DocumentStatus.PROCESSING)
                await db.commit()

                # Step 2: Parse document
                processor = DocumentProcessor()
                full_text, chunks, metadata = await processor.process_file(file_path, doc_type)

                # Step 3: Generate embeddings
                embedding_svc = EmbeddingService()
                texts = [c.content for c in chunks]
                embeddings = await embedding_svc.embed_batch(texts)

                # Step 4: Store in vector DB
                vector_store = get_vector_store()
                vector_ids = [str(_uuid.uuid4()) for _ in chunks]
                metadatas = [
                    {
                        "document_id": document_id,
                        "document_title": metadata.get("title", ""),
                        "filename": file_path.split("/")[-1],
                        "chunk_index": c.chunk_index,
                        "page_number": c.page_number or 0,
                        "collection_id": collection_id or "",
                        "owner_id": owner_id,
                    }
                    for c in chunks
                ]
                await vector_store.add_embeddings(
                    ids=vector_ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    texts=texts,
                )

                # Step 5: Save chunks to DB
                db_chunks = [
                    DocumentChunk(
                        document_id=doc_id,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        page_number=chunk.page_number,
                        token_count=chunk.token_count,
                        vector_id=vector_ids[i],
                        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
                    )
                    for i, chunk in enumerate(chunks)
                ]
                await doc_repo.create_chunks(db_chunks)

                # Step 6: Update document with extracted metadata and mark INDEXED
                await doc_repo.update_metadata(
                    doc_id,
                    title=metadata.get("title") or None,
                    author=metadata.get("author") or None,
                    total_pages=metadata.get("total_pages"),
                    total_words=metadata.get("total_words"),
                    chunk_count=len(chunks),
                )
                await doc_repo.update_status(doc_id, DocumentStatus.INDEXED)

                # Update user document count
                await user_repo.increment_usage(
                    _uuid.UUID(owner_id), documents=1
                )
                await db.commit()

                logger.info(
                    f"Document {document_id} indexed successfully",
                    chunks=len(chunks),
                )
                return {"status": "success", "chunks": len(chunks)}

            except Exception as exc:
                await db.rollback()
                await doc_repo.update_status(
                    doc_id, DocumentStatus.FAILED, error=str(exc)
                )
                await db.commit()
                logger.error(f"Ingestion failed for {document_id}: {exc}")
                raise self.retry(exc=exc)
            finally:
                await engine.dispose()

    return run_async(_run())


@celery_app.task(name="workers.delete_document_vectors")
def delete_document_vectors_task(vector_ids: list):
    """Background task to remove vectors from the store when a document is deleted."""
    async def _run():
        from app.vectorstore.store import get_vector_store
        store = get_vector_store()
        success = await store.delete_by_ids(vector_ids)
        return {"deleted": len(vector_ids), "success": success}

    return run_async(_run())
