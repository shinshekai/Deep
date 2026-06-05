"""CORS middleware — pinned origins to prevent DNS rebinding."""

from fastapi.middleware.cors import CORSMiddleware


def register_cors(app, settings):
    """Register CORS middleware with pinned allowed origins.

    Origins are pinned to localhost on the configured frontend port
    to prevent DNS rebinding attacks.  The ``localhost:3000`` fallback
    covers the default Next.js dev server.
    """
    frontend_port = getattr(settings, "frontend_port", None) or 3782
    allowed_origins = [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
        "http://localhost:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-DEEP-API-KEY"],
    )
