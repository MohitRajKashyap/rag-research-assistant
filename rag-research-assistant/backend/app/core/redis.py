"""
Redis Module
Connection management, caching utilities, and rate limiting support.
"""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Global Redis client instances
_redis_client: Optional[aioredis.Redis] = None
_cache_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get the main Redis client (for sessions, pub/sub)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def get_cache() -> aioredis.Redis:
    """Get the cache Redis client (separate DB for cache isolation)."""
    global _cache_client
    if _cache_client is None:
        cache_url = settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_CACHE_DB}"
        _cache_client = aioredis.from_url(
            cache_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _cache_client


async def close_redis() -> None:
    """Close all Redis connections on application shutdown."""
    global _redis_client, _cache_client
    if _redis_client:
        await _redis_client.aclose()
    if _cache_client:
        await _cache_client.aclose()
    logger.info("Redis connections closed")


class CacheManager:
    """
    High-level caching utilities with JSON serialization.
    Provides get/set/delete/invalidate operations.
    """

    def __init__(self, prefix: str = "rag", ttl: int = None):
        self.prefix = prefix
        self.default_ttl = ttl or settings.CACHE_TTL_SECONDS

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None if not found."""
        try:
            client = await get_cache()
            value = await client.get(self._make_key(key))
            if value is not None:
                return json.loads(value)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a cached value with optional TTL override."""
        try:
            client = await get_cache()
            serialized = json.dumps(value, default=str)
            await client.setex(
                self._make_key(key),
                ttl or self.default_ttl,
                serialized,
            )
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cached value."""
        try:
            client = await get_cache()
            await client.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern. Returns count deleted."""
        try:
            client = await get_cache()
            keys = await client.keys(self._make_key(pattern))
            if keys:
                return await client.delete(*keys)
        except Exception as e:
            logger.warning("Cache invalidate failed", pattern=pattern, error=str(e))
        return 0

    async def exists(self, key: str) -> bool:
        """Check if a cache key exists."""
        try:
            client = await get_cache()
            return bool(await client.exists(self._make_key(key)))
        except Exception:
            return False


# Shared cache instances
query_cache = CacheManager(prefix="query", ttl=1800)       # 30 min for query results
user_cache = CacheManager(prefix="user", ttl=300)           # 5 min for user data
document_cache = CacheManager(prefix="doc", ttl=3600)       # 1 hr for document metadata
embedding_cache = CacheManager(prefix="emb", ttl=86400)     # 24 hr for embeddings
