"""
Database Module
Async SQLAlchemy engine, session factory, and base model.
Supports PostgreSQL with connection pooling for production.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy.pool import NullPool
from sqlalchemy import MetaData, event
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Naming convention for constraints (for Alembic migrations)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,          # Validate connections before use
    pool_recycle=3600,           # Recycle connections every hour
    echo=settings.DEBUG,         # Log SQL in debug mode
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,       # Keep objects accessible after commit
    autoflush=True,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Automatically handles commit/rollback and session cleanup.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Database session error", error=str(exc))
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.
    Called on application startup.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        # Import all models to register them with Base
        from app.models import user, document, conversation, collection  # noqa
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections on shutdown."""
    await engine.dispose()
    logger.info("Database connections closed")
