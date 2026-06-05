"""Centralized logging configuration.

Provides a single ``configure_logging()`` entry point used during
application startup. Default format is JSON (machine-parseable for
downstream log aggregation) with file rotation; falls back to a
human-friendly colored format when the ``UDIP_LOG_FORMAT=text`` env
flag is set.

Supports per-request correlation IDs via ``contextvars.ContextVar``.
When ``UDIP_LOG_FORMAT=json`` is active and ``python-json-logger`` is
installed, logs are emitted as structured JSON with a ``correlation_id``
field.  Otherwise the correlation ID is appended to the text format.
"""

import logging
import logging.handlers
import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_CONFIGURED = False

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s :: [%(correlation_id)s] %(message)s"
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
_DEFAULT_LEVEL = os.environ.get("UDIP_LOG_LEVEL", "INFO").upper()
_FORMAT = os.environ.get("UDIP_LOG_FORMAT", "text").lower()
_MAX_BYTES = int(os.environ.get("UDIP_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
_BACKUP_COUNT = int(os.environ.get("UDIP_LOG_BACKUP_COUNT", "5"))

# ---------------------------------------------------------------------------
# Correlation-ID context variable
# ---------------------------------------------------------------------------

correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def get_or_create_correlation_id(request) -> str:  # type: ignore[no-untyped-def]
    """Return an existing correlation ID from the request header or create one.

    Accepts any object with a ``headers`` mapping (e.g. Starlette/FastAPI
    ``Request``).  The header checked is ``X-Request-ID``; if absent a UUID4
    is generated and attached to the request scope for downstream use.

    This is a *middleware helper* — callers should wire it into their own
    middleware or dependency:
    ```python
    @app.middleware("http")
    async def correlation_middleware(request, call_next):
        cid = get_or_create_correlation_id(request)
        correlation_id_var.set(cid)
        return await call_next(request)
    ```
    """
    header_name = "x-request-id"
    existing: str | None = None
    try:
        existing = request.headers.get(header_name)  # type: ignore[union-attr]
    except Exception:
        pass

    cid: str = existing or uuid.uuid4().hex

    # Expose on request scope so templates / other layers can read it.
    try:
        request.scope["correlation_id"] = cid  # type: ignore[union-attr]
    except Exception:
        pass

    correlation_id_var.set(cid)
    return cid


# ---------------------------------------------------------------------------
# Filter that injects correlation_id into every LogRecord
# ---------------------------------------------------------------------------


class CorrelationIdFilter(logging.Filter):
    """Injects ``correlation_id`` into each log record dynamically."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get() or "-"  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _build_text_formatter() -> logging.Formatter:
    fmt = os.environ.get(
        "UDIP_LOG_TEXT_FORMAT",
        _DEFAULT_FORMAT,
    )
    return logging.Formatter(fmt)


def _build_json_formatter() -> logging.Formatter:
    try:
        from pythonjsonlogger import json as jsonlogger  # type: ignore[import-untyped]

        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
            static_fields={"extra": {}},
        )
        return formatter
    except ImportError:
        logging.getLogger(__name__).warning(
            "python-json-logger not installed — falling back to text format. "
            "Install with: pip install python-json-logger"
        )
        return _build_text_formatter()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure_logging(level: str | int | None = None) -> None:
    """Configure root logger once. Idempotent — safe to call from tests."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = level or _DEFAULT_LEVEL
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear default handlers (uvicorn adds its own) and install ours
    for h in list(root.handlers):
        root.removeHandler(h)

    # Build formatter -------------------------------------------------------
    if _FORMAT == "json":
        formatter = _build_json_formatter()
    else:
        formatter = _build_text_formatter()

    # Correlation-ID filter (applied to all handlers)
    correlation_filter = CorrelationIdFilter()

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(correlation_filter)
    root.addHandler(console)

    # Rotating file handler — keeps ~5x10MB by default
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_DIR / "udip.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(correlation_filter)
        root.addHandler(file_handler)
    except OSError as exc:
        # Filesystem may be read-only in some environments — never crash
        # the app over a logging target.
        root.warning(f"Could not configure rotating log file: {exc}")

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("multipart.multipart").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger; ensures the root is configured first."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
