"""Security headers middleware — defense-in-depth response headers."""

import os

from fastapi import Request


def register_security_headers(app):
    """Register the security headers middleware on the FastAPI app.

    Adds ``X-Content-Type-Options``, ``X-Frame-Options``,
    ``Referrer-Policy``, ``COOP``, ``Permissions-Policy``, and ``CSP``
    headers to every response.  HSTS is opt-in via
    ``UDIP_HSTS_ENABLED=1`` because sending it over plain HTTP is
    meaningless.
    """

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        if os.environ.get("UDIP_HSTS_ENABLED", "").lower() in ("1", "true", "yes"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
