"""
Core Configuration Module
Centralized settings management using pydantic-settings.
All environment variables are validated and typed.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Application ---
    APP_NAME: str = "RAG Research Assistant"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    API_V1_PREFIX: str = "/api/v1"

    # --- JWT ---
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb"
    DATABASE_URL_SYNC: str = "postgresql://raguser:ragpassword@localhost:5432/ragdb"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 1
    CELERY_BROKER_URL: str = "redis://localhost:6379/2"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CACHE_TTL_SECONDS: int = 3600

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TEMPERATURE: float = 0.1

    # --- Vector Store ---
    VECTOR_STORE_TYPE: str = "faiss"
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "research_docs"

    # --- Document Processing ---
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt", "md"]
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_CHUNKS_PER_DOC: int = 500

    # --- RAG ---
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.7
    RAG_MAX_CONTEXT_LENGTH: int = 4000
    ENABLE_RERANKING: bool = True
    ENABLE_HYBRID_SEARCH: bool = True

    # --- Rate Limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # --- Monitoring ---
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"

    # --- Admin ---
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "Admin@123!"

    @validator("OPENAI_API_KEY")
    def validate_openai_key(cls, v):
        """Warn if API key not set in non-test environments."""
        if not v:
            import warnings
            warnings.warn("OPENAI_API_KEY is not set. AI features will not work.")
        return v

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance. Use as FastAPI dependency."""
    return Settings()


# Module-level settings instance for direct imports
settings = get_settings()
