"""Correlation ID middleware — attaches X-Request-ID to every request."""

from fastapi import Request
from app.services.logging_config import get_or_create_correlation_id


def register_correlation_id(app):
    """Register the correlation ID middleware on the FastAPI app.

    Reads ``X-Request-ID`` from incoming headers; if absent, generates
    a UUID4.  The ID is stored in a ``ContextVar`` so all log records
    during this request include it, and it is echoed back in the
    ``X-Request-ID`` response header for client-side tracing.
    """
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        cid = get_or_create_correlation_id(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = cid
        return response
