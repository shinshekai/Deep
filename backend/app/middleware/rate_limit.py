"""Rate limiting middleware — SlowAPI setup with configurable limits."""

import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def register_rate_limiting(app):
    """Register SlowAPI rate limiting on the FastAPI app.

    Default limit is ``100/minute`` per IP.  Operators can override via
    the ``UDIP_RATE_LIMIT`` environment variable (e.g. ``30/minute``).
    """
    rate_limit = os.environ.get("UDIP_RATE_LIMIT", "100/minute")
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[rate_limit],
        headers_enabled=True,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    return limiter
