"""
API v1 Router
Aggregates all endpoint sub-routers under /api/v1
"""
from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.collections import router as collections_router
from app.api.v1.endpoints.admin import admin_router, health_router

api_router = APIRouter()

# Public
api_router.include_router(health_router)

# Auth
api_router.include_router(auth_router)

# Core features
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(collections_router)

# Admin
api_router.include_router(admin_router)
