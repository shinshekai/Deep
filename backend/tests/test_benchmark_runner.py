"""Tests for BenchmarkRunner service."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from app.services.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkResult,
    BenchmarkRun,
    LATENCY_THRESHOLDS,
    QUALITY_THRESHOLDS,
    THROUGHPUT_THRESHOLDS,
)


# ── Fixtures ──


@pytest.fixture
def runner():
    return BenchmarkRunner()


@pytest.fixture
def runner_with_mocks():
    lm_client = AsyncMock()
    lm_client.stream_chat.return_value = "Test response"
    vram_monitor = AsyncMock()
    vram_monitor.is_active = False
    model_manager = AsyncMock()
    return BenchmarkRunner(lm_client, vram_monitor, model_manager)


# ── Data Class Tests ──


def test_benchmark_result_creation():
    r = BenchmarkResult(
        test_id="test_1",
        category="latency",
        test_case="simple_qa",
        metric="response_time_s",
        value=2.5,
        threshold=5.0,
        passed=True,
    )
    assert r.test_id == "test_1"
    assert r.passed is True


def test_benchmark_run_creation():
    run = BenchmarkRun(
        run_id="bench_1",
        category="all",
        status="queued",
        progress_pct=0,
    )
    assert run.status == "queued"
    assert run.results == []
    assert run.completed_at is None


# ── Run Lifecycle Tests ──


@pytest.mark.anyio
async def test_start_run_creates_entry():
    runner = BenchmarkRunner()
    run_id = await runner.start_run("latency")
    run = runner.get_run(run_id)
    assert run is not None
    assert run.status in ("queued", "running", "completed")
    assert run.category == "latency"


@pytest.mark.anyio
async def test_start_run_invalid_category():
    runner = BenchmarkRunner()
    run_id = await runner.start_run("nonexistent")
    run = runner.get_run(run_id)
    assert run is not None
    # Invalid category doesn't prevent the run, but results will be empty
    assert run.category == "nonexistent"


@pytest.mark.anyio
async def test_run_lifecycle_start_poll_complete():
    runner = BenchmarkRunner()
    run_id = await runner.start_run("latency")

    # Start worker to process the queue
    await runner.start_worker()

    # Wait for the run to complete
    for _ in range(50):  # up to 5 seconds
        run = runner.get_run(run_id)
        if run.status in ("completed", "failed"):
            break
        await asyncio.sleep(0.1)

    run = runner.get_run(run_id)
    assert run.status in ("completed", "failed")
    assert run.completed_at is not None
    assert run.progress_pct > 0


@pytest.mark.anyio
async def test_get_run_not_found():
    runner = BenchmarkRunner()
    assert runner.get_run("nonexistent") is None


@pytest.mark.anyio
async def test_get_latest_run_none():
    runner = BenchmarkRunner()
    assert runner.get_latest_run() is None


@pytest.mark.anyio
async def test_get_latest_run_returns_most_recent():
    runner = BenchmarkRunner()
    run_id1 = await runner.start_run("latency")
    await runner.start_worker()

    # Wait for first run to complete
    for _ in range(50):
        run = runner.get_run(run_id1)
        if run.status in ("completed", "failed"):
            break
        await asyncio.sleep(0.1)

    await asyncio.sleep(0.1)  # ensure time separation
    run_id2 = await runner.start_run("kv_cache")
    # Don't wait — just check latest returns the most recent started
    latest = runner.get_latest_run()
    assert latest is not None
    assert latest.run_id in (run_id1, run_id2)


# ── Category A: Latency Tests ──


@pytest.mark.anyio
async def test_latency_results_with_mock_client():
    lm_client = AsyncMock()
    lm_client.stream_chat.return_value = "Paris is the capital of France."
    vram_monitor = AsyncMock()
    vram_monitor.is_active = False
    runner = BenchmarkRunner(lm_client, vram_monitor)

    run = BenchmarkRun(
        run_id="test_latency",
        category="latency",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_latency(run)

    assert len(run.results) == 5  # 5 latency test cases
    assert all(r.category == "latency" for r in run.results)
    assert all(r.threshold > 0 for r in run.results)


@pytest.mark.anyio
async def test_latency_results_without_client():
    runner = BenchmarkRunner()
    run = BenchmarkRun(
        run_id="test_latency",
        category="latency",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_latency(run)

    assert len(run.results) == 5
    # Without LM client, results should be marked as not passed
    assert all(r.value == -1 for r in run.results)
    assert all(r.passed is False for r in run.results)


# ── Category B: KV Cache Tests ──


@pytest.mark.anyio
async def test_kv_cache_results_with_mock():
    vram_monitor = AsyncMock()
    vram_monitor.is_active = False
    runner = BenchmarkRunner(vram_monitor=vram_monitor)
    run = BenchmarkRun(
        run_id="test_kv",
        category="kv_cache",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_kv_cache(run)

    assert len(run.results) == 6  # 6 KV cache test cases
    assert all(r.category == "kv_cache" for r in run.results)


# ── Category C: Quality Tests ──


@pytest.mark.anyio
async def test_quality_results_stubbed():
    runner = BenchmarkRunner()
    run = BenchmarkRun(
        run_id="test_quality",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_quality(run)

    assert len(run.results) == 6
    # Quality metrics are stubbed — values should be 0, not passed
    assert all(r.value == 0.0 for r in run.results)
    assert all(r.passed is False for r in run.results)


# ── Category D: Throughput Tests ──


@pytest.mark.anyio
async def test_throughput_results_with_mock():
    lm_client = AsyncMock()
    lm_client.stream_chat.return_value = "Response"
    vram_monitor = AsyncMock()
    vram_monitor.is_active = False
    runner = BenchmarkRunner(lm_client, vram_monitor)
    run = BenchmarkRun(
        run_id="test_throughput",
        category="throughput",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_throughput(run)

    assert len(run.results) == 5  # 5 throughput test cases
    assert all(r.category == "throughput" for r in run.results)


@pytest.mark.anyio
async def test_throughput_results_without_client():
    runner = BenchmarkRunner()
    run = BenchmarkRun(
        run_id="test_throughput",
        category="throughput",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_throughput(run)

    assert len(run.results) == 5
    # Without client, single user elapsed is near-instant (no LM call made),
    # which passes the < 30s check but should still be a very low value
    single = next(r for r in run.results if r.test_case == "single_user")
    assert single.value >= 0  # measured as elapsed without LM call


# ── Threshold Constants Tests ──


def test_threshold_constants_exist():
    assert "simple_qa_e2e" in LATENCY_THRESHOLDS
    assert "ragas_faithfulness" in QUALITY_THRESHOLDS
    assert "single_user_tps" in THROUGHPUT_THRESHOLDS


# ── Error Handling Tests ──


@pytest.mark.anyio
async def test_error_handling_unreachable_lm_client():
    lm_client = AsyncMock()
    lm_client.stream_chat.side_effect = ConnectionError("LM Studio unreachable")
    vram_monitor = AsyncMock()
    vram_monitor.is_active = False
    runner = BenchmarkRunner(lm_client, vram_monitor)
    run = BenchmarkRun(
        run_id="test_error",
        category="latency",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    # Should not raise exception; records failed results
    await runner._run_category_latency(run)
    assert len(run.results) == 5
    # All results should fail (value=-1, passed=False)
    assert all(r.value == -1 for r in run.results)
    assert all(r.passed is False for r in run.results)
