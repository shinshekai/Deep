"""Input origin tracking — context for request tracing.

Works alongside existing correlation middleware (app/middleware/correlation.py).
Provides structured origin metadata accessible anywhere via ContextVar.

Pattern validated against:
- FastAPI ContextVar for request context (Python docs, StackOverflow)
- asgi-correlation-id middleware pattern (pypi)
- Structured logging with correlation IDs (Dev.to, Medium 2026)
"""

import time
from contextvars import ContextVar
from dataclasses import dataclass

request_origin_var: ContextVar["InputOrigin | None"] = ContextVar("request_origin", default=None)


@dataclass
class InputOrigin:
    source: str = "user"
    device_id: str = ""
    correlation_id: str = ""
    session_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    timestamp: float = 0.0
    method: str = ""
    path: str = ""


def get_request_origin() -> InputOrigin | None:
    return request_origin_var.get()


def get_correlation_id() -> str:
    origin = request_origin_var.get()
    return origin.correlation_id if origin else ""


def set_request_origin(origin: InputOrigin) -> object:
    return request_origin_var.set(origin)


def reset_request_origin(token: object) -> None:
    request_origin_var.reset(token)
