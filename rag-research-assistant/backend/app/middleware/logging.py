"""
Middleware
Request logging, timing, and API usage tracking.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing and status."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.time()
        try:
            response = await call_next(request)
            latency_ms = int((time.time() - start) * 1000)

            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=latency_ms,
                request_id=request_id,
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms}ms"
            return response
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                latency_ms=latency_ms,
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
