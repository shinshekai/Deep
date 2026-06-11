"""Correlation ID middleware — attaches X-Request-ID and origin tracking."""

import time

from fastapi import Request

from app.services.logging_config import get_or_create_correlation_id
from app.services.input_origin import (
    InputOrigin,
    set_request_origin,
    reset_request_origin,
)


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

        client_ip = ""
        if request.client:
            client_ip = request.client.host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        origin = InputOrigin(
            source="user",
            device_id=request.headers.get("X-Device-ID", ""),
            correlation_id=cid,
            session_id=request.headers.get("X-Session-ID", ""),
            ip_address=client_ip,
            user_agent=request.headers.get("User-Agent", ""),
            timestamp=time.time(),
            method=request.method,
            path=request.url.path,
        )
        token = set_request_origin(origin)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = cid
            return response
        finally:
            reset_request_origin(token)
