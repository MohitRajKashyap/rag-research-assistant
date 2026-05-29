"""
FastAPI Application Factory
Production-grade app setup with all middleware, routers, and lifecycle events.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import init_db, close_db
from app.core.redis import close_redis
from app.middleware.logging import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.api.v1 import api_router

logger = structlog.get_logger(__name__)

# -------------------------------------------------------
# Rate limiter
# -------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)


# -------------------------------------------------------
# Application lifecycle
# -------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    configure_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # Startup
    await init_db()
    await _seed_admin()
    logger.info("Application ready")

    yield

    # Shutdown
    await close_db()
    await close_redis()
    logger.info("Application shutdown complete")


async def _seed_admin():
    """Create the default admin user on first startup."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.user_repository import UserRepository
    from app.models.user import UserRole

    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if not await repo.email_exists(settings.ADMIN_EMAIL):
            await repo.create(
                email=settings.ADMIN_EMAIL,
                username="admin",
                password=settings.ADMIN_PASSWORD,
                full_name="System Administrator",
                role=UserRole.ADMIN,
            )
            await db.commit()
            logger.info("Admin user created", email=settings.ADMIN_EMAIL)


# -------------------------------------------------------
# Application factory
# -------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Enterprise RAG-based AI Research Assistant API",
        version=settings.APP_VERSION,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order matters — last added = first executed)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Prometheus metrics
    if settings.ENABLE_METRICS:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"},
        )

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": f"{settings.API_V1_PREFIX.replace('/api/v1', '')}/api/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


app = create_app()
