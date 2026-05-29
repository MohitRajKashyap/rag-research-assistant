"""
Collections Endpoints
POST   /collections/         — Create collection
GET    /collections/         — List user collections
GET    /collections/{id}     — Get collection
PUT    /collections/{id}     — Update collection
DELETE /collections/{id}     — Delete collection
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.models.collection import Collection
from app.schemas import SuccessResponse

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.post("/", status_code=201)
async def create_collection(
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    coll = Collection(
        owner_id=current_user.id,
        name=payload.get("name", "New Collection"),
        description=payload.get("description"),
        color=payload.get("color", "#6366f1"),
        icon=payload.get("icon", "folder"),
    )
    db.add(coll)
    await db.flush()
    await db.refresh(coll)
    return {"id": str(coll.id), "name": coll.name, "description": coll.description, "color": coll.color}


@router.get("/")
async def list_collections(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.owner_id == current_user.id).order_by(Collection.created_at.desc())
    )
    colls = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "description": c.description, "color": c.color, "document_count": c.document_count} for c in colls]


@router.get("/{collection_id}")
async def get_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id, Collection.owner_id == current_user.id)
    )
    coll = result.scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"id": str(coll.id), "name": coll.name, "description": coll.description, "color": coll.color}


@router.put("/{collection_id}")
async def update_collection(
    collection_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id, Collection.owner_id == current_user.id)
    )
    coll = result.scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    for k in ("name", "description", "color", "icon"):
        if k in payload:
            setattr(coll, k, payload[k])
    await db.flush()
    return SuccessResponse(message="Collection updated")


@router.delete("/{collection_id}", response_model=SuccessResponse)
async def delete_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id, Collection.owner_id == current_user.id)
    )
    coll = result.scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    await db.delete(coll)
    return SuccessResponse(message="Collection deleted")
