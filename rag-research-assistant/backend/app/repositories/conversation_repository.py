"""
Conversation Repository
Data access layer for conversations and messages.
"""
import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from sqlalchemy.orm import selectinload
import structlog

from app.models.conversation import Conversation, Message, MessageRole

logger = structlog.get_logger(__name__)


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conv_id: uuid.UUID) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conv_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self, conv_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(and_(Conversation.id == conv_id, Conversation.user_id == user_id))
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, title: Optional[str] = None) -> Conversation:
        conv = Conversation(user_id=user_id, title=title)
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        include_archived: bool = False,
    ) -> tuple[List[Conversation], int]:
        query = select(Conversation).where(Conversation.user_id == user_id)
        count_q = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        if not include_archived:
            query = query.where(Conversation.is_archived == False)
            count_q = count_q.where(Conversation.is_archived == False)

        total = (await self.db.execute(count_q)).scalar()
        query = query.offset(skip).limit(limit).order_by(Conversation.updated_at.desc())
        convs = (await self.db.execute(query)).scalars().all()
        return list(convs), total

    async def update(self, conv: Conversation, **kwargs) -> Conversation:
        for k, v in kwargs.items():
            if hasattr(conv, k) and v is not None:
                setattr(conv, k, v)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def delete(self, conv: Conversation) -> None:
        await self.db.delete(conv)
        await self.db.flush()

    # --- Message operations ---
    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        sources: Optional[list] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        model_used: Optional[str] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            model_used=model_used,
        )
        self.db.add(msg)
        # Increment conversation counters
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                message_count=Conversation.message_count + 1,
                total_tokens=Conversation.total_tokens + (tokens_used or 0),
            )
        )
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def get_messages(
        self, conversation_id: uuid.UUID, limit: int = 50
    ) -> List[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_message_by_id(self, msg_id: uuid.UUID) -> Optional[Message]:
        result = await self.db.execute(
            select(Message).where(Message.id == msg_id)
        )
        return result.scalar_one_or_none()

    async def update_message(self, msg: Message, **kwargs) -> Message:
        for k, v in kwargs.items():
            if hasattr(msg, k):
                setattr(msg, k, v)
        await self.db.flush()
        await self.db.refresh(msg)
        return msg
