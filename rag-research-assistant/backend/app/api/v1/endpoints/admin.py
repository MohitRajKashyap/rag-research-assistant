"""
Admin Endpoints
GET  /admin/users          — List all users
GET  /admin/users/{id}     — Get user detail
PUT  /admin/users/{id}     — Update user (role, active status)
GET  /admin/documents      — List all documents system-wide
GET  /admin/metrics        — System metrics
GET  /admin/vector-store   — Vector store stats

Health:
GET  /health               — System health check
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.database import get_db
from app.core.config import settings
from app.middleware.auth import require_admin, get_current_active_user
from app.models.user import User, UserRole
from app.models.document import Document, DocumentStatus
from app.models.conversation import Conversation, Message
from app.repositories.user_repository import UserRepository
from app.repositories.document_repository import DocumentRepository
from app.vectorstore.store import get_vector_store
from app.schemas import SuccessResponse, HealthResponse, UserAdminResponse, DocumentListResponse

router = APIRouter(tags=["Admin & Health"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
health_router = APIRouter(tags=["Health"])


# -------------------------------------------------------
# Health check (public)
# -------------------------------------------------------
@health_router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Public health endpoint for load balancers and monitoring."""
    db_status = "ok"
    redis_status = "ok"
    vector_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        await redis.ping()
    except Exception:
        redis_status = "error"

    try:
        vs = get_vector_store()
        await vs.get_collection_stats()
    except Exception:
        vector_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
        vector_store=vector_status,
    )


# -------------------------------------------------------
# Admin routes
# -------------------------------------------------------
@admin_router.get("/users", response_model=dict)
async def admin_list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str = Query(None),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    role_filter = UserRole(role) if role else None
    users, total = await repo.list_users(
        skip=(page - 1) * page_size,
        limit=page_size,
        role=role_filter,
    )
    return {
        "users": [UserAdminResponse.model_validate(u).model_dump() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.get("/users/{user_id}")
async def admin_get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse.model_validate(user)


@admin_router.put("/users/{user_id}", response_model=SuccessResponse)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed = {}
    if "role" in payload:
        allowed["role"] = UserRole(payload["role"])
    if "is_active" in payload:
        allowed["is_active"] = bool(payload["is_active"])
    if "is_verified" in payload:
        allowed["is_verified"] = bool(payload["is_verified"])

    await repo.update(user, **allowed)
    return SuccessResponse(message="User updated")


@admin_router.get("/documents")
async def admin_list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = DocumentRepository(db)
    docs, total = await repo.admin_list_all(skip=(page - 1) * page_size, limit=page_size)
    return {"documents": docs, "total": total, "page": page}


@admin_router.get("/metrics")
async def admin_metrics(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return system-wide usage metrics."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.is_active == True))
    ).scalar()
    total_docs = (await db.execute(select(func.count(Document.id)))).scalar()
    indexed_docs = (
        await db.execute(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.INDEXED)
        )
    ).scalar()
    total_convs = (await db.execute(select(func.count(Conversation.id)))).scalar()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar()
    total_tokens = (await db.execute(select(func.sum(Message.tokens_used)))).scalar() or 0
    avg_latency = (await db.execute(select(func.avg(Message.latency_ms)))).scalar() or 0

    vs_stats = {}
    try:
        vs = get_vector_store()
        vs_stats = await vs.get_collection_stats()
    except Exception:
        pass

    return {
        "users": {"total": total_users, "active": active_users},
        "documents": {"total": total_docs, "indexed": indexed_docs},
        "conversations": {"total": total_convs},
        "messages": {"total": total_messages, "total_tokens": total_tokens},
        "performance": {"avg_latency_ms": round(avg_latency or 0, 2)},
        "vector_store": vs_stats,
    }


@admin_router.get("/vector-store")
async def admin_vector_store(_: User = Depends(require_admin)):
    vs = get_vector_store()
    return await vs.get_collection_stats()
