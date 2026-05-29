"""
Document Repository
Data access layer for document and chunk operations.
"""
import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from sqlalchemy.orm import selectinload
import structlog

from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType

logger = structlog.get_logger(__name__)


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_owner(
        self, doc_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(
                and_(Document.id == doc_id, Document.owner_id == owner_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str, owner_id: uuid.UUID) -> Optional[Document]:
        """Find duplicate document by file hash."""
        result = await self.db.execute(
            select(Document).where(
                and_(Document.file_hash == file_hash, Document.owner_id == owner_id)
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        owner_id: uuid.UUID,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        doc_type: DocumentType,
        file_hash: Optional[str] = None,
        collection_id: Optional[uuid.UUID] = None,
        mime_type: Optional[str] = None,
    ) -> Document:
        doc = Document(
            owner_id=owner_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            doc_type=doc_type,
            file_hash=file_hash,
            collection_id=collection_id,
            mime_type=mime_type,
        )
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        return doc

    async def update_status(
        self,
        doc_id: uuid.UUID,
        status: DocumentStatus,
        error: Optional[str] = None,
    ) -> None:
        values = {"status": status}
        if error:
            values["processing_error"] = error
        if status == DocumentStatus.INDEXED:
            from datetime import datetime, timezone
            values["indexed_at"] = datetime.now(timezone.utc)
            values["is_indexed"] = True
        await self.db.execute(
            update(Document).where(Document.id == doc_id).values(**values)
        )

    async def update_metadata(self, doc_id: uuid.UUID, **kwargs) -> None:
        await self.db.execute(
            update(Document).where(Document.id == doc_id).values(**kwargs)
        )

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[DocumentStatus] = None,
        collection_id: Optional[uuid.UUID] = None,
    ) -> tuple[List[Document], int]:
        query = select(Document).where(Document.owner_id == owner_id)
        count_q = select(func.count(Document.id)).where(Document.owner_id == owner_id)

        if status:
            query = query.where(Document.status == status)
            count_q = count_q.where(Document.status == status)
        if collection_id:
            query = query.where(Document.collection_id == collection_id)
            count_q = count_q.where(Document.collection_id == collection_id)

        total = (await self.db.execute(count_q)).scalar()
        query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())
        docs = (await self.db.execute(query)).scalars().all()
        return list(docs), total

    async def delete(self, doc: Document) -> None:
        await self.db.delete(doc)
        await self.db.flush()

    # --- Chunk operations ---
    async def create_chunks(self, chunks: List[DocumentChunk]) -> None:
        self.db.add_all(chunks)
        await self.db.flush()

    async def get_chunks_by_doc(self, doc_id: uuid.UUID) -> List[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_chunk_by_vector_id(self, vector_id: str) -> Optional[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.vector_id == vector_id)
        )
        return result.scalar_one_or_none()

    async def delete_chunks_by_doc(self, doc_id: uuid.UUID) -> None:
        from sqlalchemy import delete
        await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )

    async def admin_list_all(
        self, skip: int = 0, limit: int = 20
    ) -> tuple[List[Document], int]:
        total = (await self.db.execute(select(func.count(Document.id)))).scalar()
        docs = (
            await self.db.execute(
                select(Document).offset(skip).limit(limit).order_by(Document.created_at.desc())
            )
        ).scalars().all()
        return list(docs), total
