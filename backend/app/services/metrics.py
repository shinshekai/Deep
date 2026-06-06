"""Prometheus metrics for UDIP backend.

Defines request count, error rate, latency histogram, and active
connections.  The ``MetricsMiddleware`` populates them automatically;
individual services can use the counters/histograms directly for
custom instrumentation.

Usage::

    from app.services.metrics import REQUEST_COUNT, LLM_LATENCY
    REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/query", status="200").inc()
"""

import time
import logging
from typing import Callable

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── Metric definitions ───────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "udip_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "udip_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

ERROR_COUNT = Counter(
    "udip_http_errors_total",
    "Total HTTP error responses (status >= 400)",
    ["method", "endpoint", "status"],
)

ACTIVE_WS_CONNECTIONS = Gauge(
    "udip_active_websocket_connections",
    "Currently active WebSocket connections",
)

LLM_REQUEST_COUNT = Counter(
    "udip_llm_requests_total",
    "Total LLM requests to LM Studio",
    ["method"],
)

LLM_LATENCY = Histogram(
    "udip_llm_latency_seconds",
    "LM Studio request latency in seconds",
    ["method"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

DEEP_RESEARCH_ACTIVE = Gauge(
    "udip_deep_research_active",
    "Number of active deep research background tasks",
)

UPLOAD_SIZE = Histogram(
    "udip_upload_size_bytes",
    "Document upload size in bytes",
    ["kb_name"],
    buckets=(1024, 10240, 102400, 1048576, 10485760, 52428800),
)

FACT_EXTRACTION_FAILURES = Counter(
    "memory_fact_extraction_failures_total",
    "Total fact-extraction failures (silent before audit fix)",
)

APP_INFO = Info(
    "udip",
    "UDIP application information",
)


def _normalise_endpoint(path: str) -> str:
    """Collapse path parameters into placeholders to avoid high-cardinality labels.

    /api/v1/knowledge/bases/my-kb → /api/v1/knowledge/bases/{kb_name}
    /api/v1/knowledge/bases/my-kb/documents/doc-123 → /api/v1/knowledge/bases/{kb_name}/documents/{doc_id}
    """
    parts = path.split("/")
    result: list[str] = []
    for part in parts:
        if part.startswith("session_") or (len(part) > 8 and "-" in part):
            result.append("{id}")
        elif part.startswith("run_"):
            result.append("{run_id}")
        else:
            result.append(part)
    return "/".join(result)


# ── Middleware ────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for every HTTP request.

    Replaces the inline latency-metrics code that was previously in the
    ``@app.middleware("http")`` block in ``main.py``.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip the /metrics endpoint itself to avoid recursion.
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = _normalise_endpoint(request.url.path)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Let Starlette's exception handlers deal with it; record
            # the error metric and re-raise.
            ERROR_COUNT.labels(method=method, endpoint=endpoint, status="500").inc()
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="500").inc()
            raise

        elapsed = time.perf_counter() - start
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)

        if response.status_code >= 400:
            ERROR_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()

        # Record for error-rate alerting
        try:
            from app.services.alerting import get_alert_state
            get_alert_state().record_request(response.status_code)
        except Exception:
            pass

        return response


# ── /metrics endpoint ────────────────────────────────────────────────

def metrics_endpoint(request: Request) -> Response:
    """Return all Prometheus metrics in the exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
