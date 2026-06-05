"""Authentication middleware — token validation + error sanitization."""

import re
import time
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app import state

logger = logging.getLogger(__name__)


def register_auth(app, settings):
    """Register the authentication middleware on the FastAPI app.

    Validates ``X-DEEP-API-KEY``, ``Authorization: Bearer``, or
    ``?token=`` query parameter against the configured
    ``ws_auth_token``.  Also sanitizes error messages to prevent
    internal path disclosure, and records latency metrics.
    """
    @app.middleware("http")
    async def secure_http_middleware(request: Request, call_next):
        # 1. CORS Preflight & Open Routes Bypass
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in ["/docs", "/redoc", "/openapi.json", "/api/v1/health"]:
            return await call_next(request)

        # 2. Authentication check
        from app.services.security import safe_compare
        token = settings.ws_auth_token
        if token:
            api_key = request.headers.get("X-DEEP-API-KEY") or request.headers.get("x-deep-api-key")
            auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header.split(" ", 1)[1]

            if not api_key:
                api_key = request.query_params.get("token")

            if not safe_compare(api_key, token):
                client = request.client.host if request.client else "unknown"
                logger.warning(
                    "auth_failure: path=%s remote=%s method=%s "
                    "has_header=%s has_bearer=%s has_query_token=%s",
                    path,
                    client,
                    request.method,
                    bool(request.headers.get("X-DEEP-API-KEY")),
                    bool(auth_header and auth_header.startswith("Bearer ")),
                    "token" in request.query_params,
                )
                from app.services.audit import audit
                audit("auth.http_failure", path=path, remote=client,
                      method=request.method,
                      has_header=bool(request.headers.get("X-DEEP-API-KEY")),
                      has_bearer=bool(auth_header and auth_header.startswith("Bearer ")))
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "error": "Unauthorized",
                        "message": "Access denied. Valid API Token is missing or invalid."
                    }
                )

        # 3. Request processing with error sanitization
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as exc:
            err_msg = str(exc)
            sanitized_msg = re.sub(r"[A-Za-z]:\\[Uu]sers\\[^\\]+", r"C:\\Users\\<user>", err_msg)
            logger.error(f"Internal Server Error: {sanitized_msg}", exc_info=False)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "InternalServerError",
                    "message": "An unexpected server error occurred.",
                }
            )

        # 4. Latency metric
        elapsed_ms = (time.time() - start_time) * 1000
        state._latest_metrics["latency_ms"] = int(elapsed_ms)
        response.headers["X-E2E-Latency-ms"] = str(round(elapsed_ms, 2))
        return response
