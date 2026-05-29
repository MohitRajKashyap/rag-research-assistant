"""
Conversation Models
Stores chat sessions, messages, and source citations.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Text, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        uuid.UUID if False else __import__('sqlalchemy.dialects.postgresql', fromlist=['UUID']).UUID(as_uuid=True),
        primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        __import__('sqlalchemy.dialects.postgresql', fromlist=['UUID']).UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    conversation_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} [{self.message_count} msgs]>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        __import__('sqlalchemy.dialects.postgresql', fromlist=['UUID']).UUID(as_uuid=True),
        primary_key=True, default=uuid.uuid4, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        __import__('sqlalchemy.dialects.postgresql', fromlist=['UUID']).UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # RAG metadata
    sources: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)

    # Feedback
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback_rating: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-5

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationship
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.role} in {self.conversation_id}>"
