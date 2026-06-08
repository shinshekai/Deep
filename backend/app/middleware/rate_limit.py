"""Rate limiting middleware — SlowAPI setup with configurable limits."""

import hashlib
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _user_or_ip(request):
    """Rate limit key: prefer API token identity, fall back to IP."""
    for header in ("x-deep-api-key", "authorization"):
        value = request.headers.get(header, "")
        if value:
            token = value.removeprefix("Bearer ").strip()
            if token:
                return "user:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    return "ip:" + get_remote_address(request)


def register_rate_limiting(app):
    """Register SlowAPI rate limiting on the FastAPI app.

    Default limit is ``100/minute`` per user (authenticated) or per IP
    (unauthenticated). Operators can override via the ``UDIP_RATE_LIMIT``
    environment variable (e.g. ``30/minute``).
    """
    rate_limit = os.environ.get("UDIP_RATE_LIMIT", "100/minute")
    limiter = Limiter(
        key_func=_user_or_ip,
        default_limits=[rate_limit],
        headers_enabled=True,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    return limiter
