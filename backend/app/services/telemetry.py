"""OpenTelemetry tracing utilities for UDIP core services.

Provides a thin wrapper so callers never crash when opentelemetry is not
installed — the helpers silently become no-ops.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Conditional import ──────────────────────────────────────────────

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    _tracer = trace.get_tracer("udip.backend")
    _OTEL_AVAILABLE = True
except ImportError:
    _tracer = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False


def is_enabled() -> bool:
    """Return True if OpenTelemetry SDK is installed and active."""
    return _OTEL_AVAILABLE


# ── Span helpers ────────────────────────────────────────────────────

@contextmanager
def trace_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
):
    """Context-manager that wraps a block in an OTel span.

    Usage::

        with trace_span("retrieval.tree_search", {"kb": kb_name}):
            results = await tree_search.search(...)

    When opentelemetry is absent the block executes normally without overhead.
    """
    if not _OTEL_AVAILABLE or _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, _safe_attr(v))
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


def start_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
):
    """Start a span and return it (caller must end it)."""
    if not _OTEL_AVAILABLE or _tracer is None:
        return _NoOpSpan()

    span = _tracer.start_span(name)
    if attributes:
        for k, v in attributes.items():
            span.set_attribute(k, _safe_attr(v))
    return span


def end_span(span, status_ok: bool = True, error: Optional[str] = None):
    """End a span started with start_span()."""
    if isinstance(span, _NoOpSpan):
        return
    if not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.trace import StatusCode as SC
        if error:
            span.set_status(SC.ERROR, error)
        elif status_ok:
            span.set_status(SC.OK)
        span.end()
    except Exception:
        pass


def add_event(name: str, attributes: Optional[dict[str, Any]] = None):
    """Add an event to the current active span (if any)."""
    if not _OTEL_AVAILABLE:
        return
    span = trace.get_current_span()
    if span and span.is_recording():
        safe_attrs = {k: _safe_attr(v) for k, v in (attributes or {}).items()}
        span.add_event(name, attributes=safe_attrs)


# ── Internal helpers ────────────────────────────────────────────────

def _safe_attr(value: Any) -> Any:
    """Coerce values to OTel-compatible attribute types (str, int, float, bool)."""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class _NoOpSpan:
    """Drop-in replacement when OTel is absent."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args, **kwargs) -> None:
        pass

    def add_event(self, *args, **kwargs) -> None:
        pass

    def record_exception(self, *args, **kwargs) -> None:
        pass

    def end(self) -> None:
        pass

    def is_recording(self) -> bool:
        return False
