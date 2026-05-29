"""
Chat Endpoints
POST /chat/                        — Send message (non-streaming)
POST /chat/stream                  — SSE streaming response
WS   /chat/ws/{conversation_id}    — WebSocket streaming
GET  /chat/conversations           — List conversations
GET  /chat/conversations/{id}      — Get conversation with messages
DELETE /chat/conversations/{id}    — Delete conversation
PUT  /chat/conversations/{id}      — Update (title, archive)
POST /chat/messages/{id}/feedback  — Rate a message
GET  /chat/messages/{id}/bookmark  — Bookmark toggle
"""
import uuid
import json
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.models.conversation import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository
from app.rag.pipeline import get_rag_pipeline
from app.schemas import (
    ChatRequest, ChatResponse, ConversationResponse,
    ConversationListResponse, MessageFeedbackRequest,
    ConversationUpdateRequest, SuccessResponse,
)
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


def _build_history(messages) -> list:
    """Convert DB messages to LLM history format."""
    return [
        {"role": m.role.value, "content": m.content}
        for m in messages[-10:]  # last 5 turns
        if m.role != MessageRole.SYSTEM
    ]


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a complete AI response (non-streaming)."""
    conv_repo = ConversationRepository(db)
    user_repo = UserRepository(db)
    pipeline = get_rag_pipeline()

    # Get or create conversation
    if payload.conversation_id:
        conv = await conv_repo.get_by_id_and_user(payload.conversation_id, current_user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = _build_history(conv.messages)
    else:
        conv = await conv_repo.create(user_id=current_user.id)
        history = []

    # Save user message
    await conv_repo.add_message(
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=payload.message,
    )

    # Run RAG pipeline
    result = await pipeline.query(
        question=payload.message,
        conversation_history=history,
        collection_id=str(payload.collection_id) if payload.collection_id else None,
        top_k=payload.top_k,
    )

    # Save assistant message
    from app.schemas.conversation import MessageSource
    sources_data = [MessageSource(**s) if isinstance(s, dict) else s for s in result["sources"]]
    assistant_msg = await conv_repo.add_message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content=result["content"],
        sources=[s.model_dump() if hasattr(s, "model_dump") else s for s in sources_data],
        tokens_used=result["tokens_used"],
        latency_ms=result["latency_ms"],
        model_used=result["model"],
    )

    # Auto-title conversation on first exchange
    if conv.message_count <= 2 and not conv.title:
        title = payload.message[:60] + ("..." if len(payload.message) > 60 else "")
        await conv_repo.update(conv, title=title)

    # Track usage
    await user_repo.increment_usage(
        current_user.id,
        queries=1,
        tokens=result["tokens_used"],
    )

    return ChatResponse(
        message_id=assistant_msg.id,
        conversation_id=conv.id,
        content=result["content"],
        sources=sources_data,
        tokens_used=result["tokens_used"],
        latency_ms=result["latency_ms"],
        model_used=result["model"],
    )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming chat via Server-Sent Events (SSE).
    Returns text/event-stream where each event is a JSON chunk.
    """
    conv_repo = ConversationRepository(db)
    pipeline = get_rag_pipeline()

    if payload.conversation_id:
        conv = await conv_repo.get_by_id_and_user(payload.conversation_id, current_user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = _build_history(conv.messages)
    else:
        conv = await conv_repo.create(user_id=current_user.id)
        history = []

    await conv_repo.add_message(
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=payload.message,
    )

    async def event_generator():
        # Send conversation ID immediately
        yield f"data: {json.dumps({'type': 'init', 'conversation_id': str(conv.id)})}\n\n"

        full_content = ""
        sources_data = []

        async for chunk in pipeline.stream_query(
            question=payload.message,
            conversation_history=history,
            collection_id=str(payload.collection_id) if payload.collection_id else None,
            top_k=payload.top_k,
        ):
            if chunk["type"] == "sources":
                sources_data = chunk["sources"]
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "token":
                full_content += chunk.get("content", "")
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "done":
                # Persist complete response
                try:
                    msg = await conv_repo.add_message(
                        conversation_id=conv.id,
                        role=MessageRole.ASSISTANT,
                        content=full_content,
                        sources=sources_data,
                        model_used=pipeline.model,
                    )
                    yield f"data: {json.dumps({'type': 'done', 'message_id': str(msg.id)})}\n\n"
                except Exception as e:
                    logger.error("Failed to persist stream response", error=str(e))
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
            elif chunk["type"] == "error":
                yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
):
    """
    WebSocket endpoint for real-time chat.
    Client sends: {"message": "...", "collection_id": null}
    Server streams: JSON chunks matching StreamChunk schema
    """
    await websocket.accept()
    pipeline = get_rag_pipeline()

    try:
        # Validate token
        from app.core.security import get_token_subject
        from app.core.database import AsyncSessionLocal
        from app.repositories.user_repository import UserRepository
        import uuid as _uuid

        user_id = get_token_subject(token, "access")
        async with AsyncSessionLocal() as db:
            user_repo = UserRepository(db)
            user = await user_repo.get_by_id(_uuid.UUID(user_id))
            if not user or not user.is_active:
                await websocket.send_json({"type": "error", "error": "Unauthorized"})
                await websocket.close()
                return

        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            collection_id = data.get("collection_id")

            if not message.strip():
                continue

            async for chunk in pipeline.stream_query(
                question=message,
                collection_id=collection_id,
            ):
                await websocket.send_json(chunk)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", conversation_id=conversation_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


# -------------------------------------------------------
# Conversation management
# -------------------------------------------------------
@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    convs, total = await repo.list_by_user(
        user_id=current_user.id,
        skip=(page - 1) * page_size,
        limit=page_size,
        include_archived=include_archived,
    )
    return ConversationListResponse(
        conversations=convs, total=total, page=page, page_size=page_size
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id_and_user(conversation_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id_and_user(conversation_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await repo.update(conv, **payload.model_dump(exclude_none=True))


@router.delete("/conversations/{conversation_id}", response_model=SuccessResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id_and_user(conversation_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await repo.delete(conv)
    return SuccessResponse(message="Conversation deleted")


@router.post("/messages/{message_id}/feedback", response_model=SuccessResponse)
async def message_feedback(
    message_id: uuid.UUID,
    payload: MessageFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    msg = await repo.get_message_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await repo.update_message(msg, feedback_rating=payload.rating)
    return SuccessResponse(message="Feedback saved")


@router.post("/messages/{message_id}/bookmark", response_model=SuccessResponse)
async def toggle_bookmark(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    msg = await repo.get_message_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await repo.update_message(msg, is_bookmarked=not msg.is_bookmarked)
    return SuccessResponse(message="Bookmark toggled", data={"bookmarked": not msg.is_bookmarked})
