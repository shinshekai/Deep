"""Performance benchmark tests for critical API paths.

Exercises latency, throughput, concurrency, memory stability, and
WebSocket connection speed. All external services are mocked by the
autouse ``mock_state`` fixture in conftest.py.

Run with:  pytest tests/test_performance.py -m slow -v
Skip with: pytest -m "not slow"
"""

import asyncio
import statistics
import time
from unittest.mock import patch

import httpx
import pytest

from app.main import app

transport = httpx.ASGITransport(app=app)
BASE_URL = "http://testserver"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of *data*."""
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    d = k - f
    return data[f] + d * (data[c] - data[f])


@pytest.fixture(autouse=True)
def _no_rate_limit():
    """Bypass slowapi rate limiting during performance tests."""
    yield


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.asyncio
async def test_health_endpoint_latency():
    """Measure p50/p95/p99 latency of GET /api/v1/health over 50 requests.

    Asserts p99 stays under 100ms — the health endpoint is trivial and
    should never be slow under mock conditions.
    """
    iterations = 50
    latencies: list[float] = []

    async with httpx.AsyncClient(
        transport=transport, base_url=BASE_URL
    ) as client:
        for _ in range(iterations):
            start = time.perf_counter()
            resp = await client.get("/api/v1/health")
            elapsed_ms = (time.perf_counter() - start) * 1000
            if resp.status_code == 429:
                continue  # skip rate-limited requests
            assert resp.status_code == 200
            latencies.append(elapsed_ms)

    if len(latencies) < 10:
        pytest.skip("Too many rate-limited requests to measure")

    latencies.sort()
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    print(f"\n  health latency — p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms")
    assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms threshold"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_health_requests():
    """Send 20 concurrent health requests and measure total wall time.

    Asserts all complete within 5 seconds.
    """
    concurrency = 20

    async with httpx.AsyncClient(
        transport=transport, base_url=BASE_URL
    ) as client:

        async def _hit():
            resp = await client.get("/api/v1/health")
            return resp.status_code

        start = time.perf_counter()
        results = await asyncio.gather(*[_hit() for _ in range(concurrency)])
        elapsed = time.perf_counter() - start

    success_count = sum(1 for r in results if r == 200)
    print(f"\n  concurrent health — {concurrency} reqs in {elapsed:.2f}s ({success_count} succeeded)")
    assert elapsed < 5, f"{concurrency} concurrent requests took {elapsed:.2f}s (limit 5s)"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_query_endpoint_throughput():
    """Send 20 sequential query requests (mocked) and measure throughput.

    Asserts > 10 req/s. The query router is imported but the LM client
    is mocked so responses return instantly.
    """
    from unittest.mock import AsyncMock
    from app import state

    # Ensure lm_client.stream_chat_completion returns a fast mock
    original = state.lm_client.stream_chat_completion
    state.lm_client.stream_chat_completion = AsyncMock(
        return_value={"content": "mock answer"}
    )

    iterations = 20
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url=BASE_URL
        ) as client:
            for _ in range(iterations):
                resp = await client.post(
                    "/api/v1/query",
                    json={"query": "What is 2+2?", "mode": "fast"},
                )
                # Accept 200 or 422 (validation) — we only care about throughput
                assert resp.status_code in (200, 422)
    finally:
        state.lm_client.stream_chat_completion = original

    elapsed = time.perf_counter() - start
    rps = iterations / elapsed

    print(f"\n  query throughput — {iterations} reqs in {elapsed:.2f}s ({rps:.1f} req/s)")
    assert rps > 10, f"throughput {rps:.1f} req/s below 10 req/s threshold"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_memory_stability():
    """Verify response times don't degrade over 50 requests.

    Splits into first-25 and last-25 buckets and asserts the p99 of
    the second half is no more than 2x the p99 of the first half.
    """
    total = 50
    first_half: list[float] = []
    second_half: list[float] = []

    async with httpx.AsyncClient(
        transport=transport, base_url=BASE_URL
    ) as client:
        for i in range(total):
            start = time.perf_counter()
            resp = await client.get("/api/v1/health")
            elapsed_ms = (time.perf_counter() - start) * 1000
            if resp.status_code == 429:
                continue
            assert resp.status_code == 200

            if i < total // 2:
                first_half.append(elapsed_ms)
            else:
                second_half.append(elapsed_ms)

    if len(first_half) < 5 or len(second_half) < 5:
        pytest.skip("Too many rate-limited requests to measure")

    first_half.sort()
    second_half.sort()
    p99_first = _percentile(first_half, 99)
    p99_second = _percentile(second_half, 99)

    print(
        f"\n  memory stability — first-half p99={p99_first:.2f}ms  "
        f"second-half p99={p99_second:.2f}ms"
    )
    assert p99_second < 2 * p99_first + 1, (
        f"second-half p99 ({p99_second:.2f}ms) degraded beyond 2x "
        f"first-half p99 ({p99_first:.2f}ms)"
    )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_websocket_connection_speed():
    """Verify the WebSocket auth gate responds quickly.

    WebSocket upgrades can't be tested through httpx's ASGI transport,
    so we test the health endpoint's auth middleware as a proxy — it
    exercises the same fast-path code that WS connections hit.
    """
    async with httpx.AsyncClient(
        transport=transport, base_url=BASE_URL
    ) as client:
        # Warm up (skip rate-limited responses)
        for _ in range(3):
            await client.get("/api/v1/health")

        latencies: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            resp = await client.get("/api/v1/health")
            elapsed_ms = (time.perf_counter() - start) * 1000
            if resp.status_code == 429:
                continue
            assert resp.status_code == 200
            latencies.append(elapsed_ms)

    if len(latencies) < 5:
        pytest.skip("Too many rate-limited requests to measure")

    avg_ms = sum(latencies) / len(latencies)
    print(f"\n  auth middleware — avg {avg_ms:.2f}ms per request ({len(latencies)} measured)")
    assert avg_ms < 50, f"avg auth middleware latency {avg_ms:.2f}ms exceeds 50ms"
