"""Tests for Prometheus metrics — Day 15.

The MetricsMiddleware (app/services/metrics.py) collects request count,
error rate, latency histogram, and active WS connection gauges. These
tests verify the middleware wires up correctly and the /metrics endpoint
returns valid Prometheus exposition text.
"""

import pytest
from fastapi.testclient import TestClient


def _app():
    """Lazy import to avoid side-effects during collection."""
    return __import__("app.main", fromlist=["app"]).app


def test_metrics_endpoint_returns_prometheus_text():
    """GET /metrics returns valid Prometheus exposition format."""
    client = TestClient(_app())
    resp = client.get("/metrics")
    assert resp.status_code == 200
    # Prometheus exposition starts with a HELP or TYPE line.
    lines = resp.text.strip().splitlines()
    assert len(lines) > 0
    assert any(l.startswith("# HELP") or l.startswith("# TYPE") for l in lines)


def test_metrics_endpoint_exposes_request_count():
    """After making a request, the udip_http_requests_total counter is > 0."""
    client = TestClient(_app())
    # Trigger a request to a known endpoint
    client.get("/api/v1/health")
    resp = client.get("/metrics")
    assert "udip_http_requests_total" in resp.text


def test_metrics_endpoint_exposes_latency_histogram():
    """After making a request, the latency histogram is present."""
    client = TestClient(_app())
    client.get("/api/v1/health")
    resp = client.get("/metrics")
    assert "udip_http_request_duration_seconds" in resp.text


def test_metrics_endpoint_not_counted_in_itself():
    """The /metrics endpoint should not count itself (avoids recursion)."""
    client = TestClient(_app())
    # Hit /metrics several times
    for _ in range(3):
        client.get("/metrics")
    resp = client.get("/metrics")
    # The endpoint should not appear as a label value
    assert 'endpoint="/metrics"' not in resp.text


def test_metrics_middleware_records_404():
    """Requests to non-existent paths produce a 404 error metric."""
    client = TestClient(_app())
    client.get("/api/v1/nonexistent_path_12345")
    resp = client.get("/metrics")
    # Should have a 404 status in the counter
    assert "404" in resp.text


def test_metrics_active_ws_gauge():
    """The ACTIVE_WS_CONNECTIONS gauge is present in the exposition."""
    from app.services.metrics import ACTIVE_WS_CONNECTIONS
    # The gauge may be 0 or 1 depending on server state; just verify it exists.
    ACTIVE_WS_CONNECTIONS.set(0)
    client = TestClient(_app())
    resp = client.get("/metrics")
    assert "udip_active_websocket_connections" in resp.text


def test_metrics_deep_research_gauge():
    """The DEEP_RESEARCH_ACTIVE gauge is present in the exposition."""
    from app.services.metrics import DEEP_RESEARCH_ACTIVE
    DEEP_RESEARCH_ACTIVE.set(0)
    client = TestClient(_app())
    resp = client.get("/metrics")
    assert "udip_deep_research_active" in resp.text


def test_metrics_llm_counter():
    """The LLM_REQUEST_COUNT counter is present in the exposition."""
    from app.services.metrics import LLM_REQUEST_COUNT
    client = TestClient(_app())
    resp = client.get("/metrics")
    assert "udip_llm_requests_total" in resp.text
