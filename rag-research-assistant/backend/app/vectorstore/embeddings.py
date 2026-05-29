"""
Embedding Service
Generates vector embeddings using OpenAI's API with Redis caching.
Supports batch processing and retry logic.
"""
import hashlib
import asyncio
from typing import List, Optional
import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.redis import embedding_cache

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Manages text-to-vector embedding generation.
    Caches embeddings in Redis to avoid redundant API calls.
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.batch_size = 100   # OpenAI supports up to 2048 inputs per request
        self.max_retries = 3
        self.retry_delay = 1.0

    def _cache_key(self, text: str) -> str:
        """Generate a deterministic cache key from text content."""
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()[:32]

    async def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        Returns cached embedding if available.
        """
        cache_key = self._cache_key(text)
        cached = await embedding_cache.get(cache_key)
        if cached:
            return cached

        embedding = await self._call_api([text])
        if embedding:
            await embedding_cache.set(cache_key, embedding[0])
            return embedding[0]
        return []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts efficiently.
        Uses cache for already-embedded texts, batches new ones.
        """
        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached = await embedding_cache.get(cache_key)
            if cached:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        logger.info(
            "Embedding batch",
            total=len(texts),
            cached=len(texts) - len(uncached_texts),
            to_embed=len(uncached_texts),
        )

        # Embed uncached texts in batches
        if uncached_texts:
            all_embeddings: List[List[float]] = []
            for batch_start in range(0, len(uncached_texts), self.batch_size):
                batch = uncached_texts[batch_start : batch_start + self.batch_size]
                batch_embeddings = await self._call_api(batch)
                all_embeddings.extend(batch_embeddings)

                # Cache each result
                for text, emb in zip(batch, batch_embeddings):
                    cache_key = self._cache_key(text)
                    await embedding_cache.set(cache_key, emb)

            # Map results back to original positions
            for i, emb in zip(uncached_indices, all_embeddings):
                results[i] = emb

        return [r for r in results if r is not None]

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI Embeddings API with retry logic."""
        # Truncate texts that exceed token limits
        cleaned = [t[:8000] if len(t) > 8000 else t for t in texts]

        for attempt in range(self.max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=cleaned,
                    encoding_format="float",
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.warning(
                    "Embedding API error",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error("Embedding API failed after retries", error=str(e))
                    # Return zero vectors as fallback
                    return [[0.0] * 1536] * len(texts)

        return [[0.0] * 1536] * len(texts)

    async def get_embedding_dimension(self) -> int:
        """Return embedding vector dimension for the configured model."""
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dimensions.get(self.model, 1536)


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
