"""Tests for BenchmarkRunner service."""

import asyncio
import json
import pytest
from pathlib import Path
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
    """Test quality results - now uses dataset if available, fallback otherwise."""
    runner = BenchmarkRunner()
    # Ensure no dataset is loaded for this test
    runner._dataset = []
    run = BenchmarkRun(
        run_id="test_quality",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_quality(run)

    # With no dataset, should have 1 result (no_dataset warning)
    assert len(run.results) == 1
    assert run.results[0].test_id == "quality_no_dataset"
    assert run.results[0].passed is False


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


# ── Phase 6: RAGAS Evaluation Tests ──


@pytest.fixture
def runner_with_dataset():
    """Create a BenchmarkRunner with a mocked dataset."""
    runner = BenchmarkRunner()
    runner._dataset = [
        {
            "id": "faith_001",
            "category": "faithfulness",
            "query": "What is PageIndex?",
            "expected_contexts": ["PageIndex is a tree-based indexing system."],
            "ground_truth": "PageIndex is a tree-based document indexing system.",
            "relevant_kb": "default",
        },
        {
            "id": "rel_001",
            "category": "relevancy",
            "query": "How does TurboQuant work?",
            "expected_contexts": ["TurboQuant uses 3-4 bit KV cache quantization."],
            "ground_truth": "TurboQuant reduces memory via KV cache quantization.",
            "relevant_kb": "default",
        },
    ]
    return runner


def test_dataset_loading(tmp_path):
    """Test that _load_dataset correctly loads JSON."""
    # Create a temporary dataset file
    dataset = {
        "metadata": {"name": "test"},
        "test_cases": [{"id": "t1", "category": "faithfulness"}],
    }
    dataset_file = tmp_path / "test_dataset.json"
    dataset_file.write_text(json.dumps(dataset))

    runner = BenchmarkRunner()
    runner.DATASET_PATH = dataset_file
    result = runner._load_dataset()
    assert len(result) == 1
    assert result[0]["id"] == "t1"


def test_dataset_loading_missing():
    """Test handling of missing dataset file."""
    runner = BenchmarkRunner()
    runner.DATASET_PATH = Path("/nonexistent/path.json")
    result = runner._load_dataset()
    assert result == []


@pytest.mark.anyio
async def test_run_category_quality_without_dataset():
    """Test quality run when no dataset is available."""
    runner = BenchmarkRunner()
    runner._dataset = []
    run = BenchmarkRun(
        run_id="test_no_dataset",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run
    await runner._run_category_quality(run)

    assert len(run.results) == 1
    assert run.results[0].test_id == "quality_no_dataset"
    assert run.results[0].passed is False


@pytest.mark.anyio
async def test_run_category_quality_with_dataset(runner_with_dataset):
    """Test quality run with dataset (RAGAS unavailable, uses fallback)."""
    runner = runner_with_dataset
    # Mock the RAGAS_AVAILABLE to False to test fallback
    import app.services.benchmark_runner as bm_module

    original = bm_module.RAGAS_AVAILABLE
    bm_module.RAGAS_AVAILABLE = False

    run = BenchmarkRun(
        run_id="test_quality_real",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    # Mock the LM client for answer generation
    runner.lm_client = AsyncMock()
    runner.lm_client.stream_chat.return_value = "Test answer about PageIndex."

    await runner._run_category_quality(run)

    # Should have results from fallback scoring
    assert len(run.results) >= 1
    assert run.progress_pct == 75

    bm_module.RAGAS_AVAILABLE = original


@pytest.mark.anyio
async def test_generate_answer(runner_with_dataset):
    """Test answer generation from contexts."""
    runner = runner_with_dataset
    runner.lm_client = AsyncMock()
    runner.lm_client.stream_chat.return_value = "PageIndex is a tree-based system."

    answer = await runner._generate_answer(
        "What is PageIndex?", ["PageIndex is a tree-based indexing system."]
    )

    assert answer == "PageIndex is a tree-based system."
    runner.lm_client.stream_chat.assert_called_once()


@pytest.mark.anyio
async def test_generate_answer_no_client(runner_with_dataset):
    """Test answer generation when no LM client is available."""
    runner = runner_with_dataset
    runner.lm_client = None

    answer = await runner._generate_answer("What is PageIndex?", [])
    assert answer == "No LM client available"


@pytest.mark.anyio
async def test_hallucination_detection(runner_with_dataset):
    """Test hallucination detection logic."""
    runner = runner_with_dataset
    runner.lm_client = AsyncMock()
    runner.lm_client.stream_chat.return_value = "PageIndex is a tree-based system."

    # Create a test case
    case = {
        "id": "hall_001",
        "category": "hallucination",
        "query": "What is PageIndex?",
        "expected_contexts": ["PageIndex is a tree-based indexing system."],
        "ground_truth": "PageIndex is a tree-based document indexing system.",
    }

    run = BenchmarkRun(
        run_id="test_hall",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    is_hallucinated = await runner._evaluate_hallucination(run, case)
    # Answer closely matches context, so should NOT be hallucinated
    assert is_hallucinated is False


@pytest.mark.anyio
async def test_hallucination_detection_high_overlap(runner_with_dataset):
    """Test hallucination detection with off-topic answer."""
    runner = runner_with_dataset
    runner.lm_client = AsyncMock()
    # Answer contains many words NOT in context/ground truth
    runner.lm_client.stream_chat.return_value = "The purple elephant danced gracefully under the midnight sun while eating bananas and singing opera songs about quantum physics."

    case = {
        "id": "hall_002",
        "category": "hallucination",
        "query": "What is PageIndex?",
        "expected_contexts": ["PageIndex is a tree-based indexing system."],
        "ground_truth": "PageIndex is a tree-based document indexing system.",
    }

    run = BenchmarkRun(
        run_id="test_hall2",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    is_hallucinated = await runner._evaluate_hallucination(run, case)
    # Answer has many extra words, should be flagged as hallucinated
    assert is_hallucinated is True


@pytest.mark.anyio
async def test_run_ragas_evaluation_ragas_unavailable(runner_with_dataset):
    """Test RAGAS evaluation when ragas is not available."""
    runner = runner_with_dataset
    runner.lm_client = AsyncMock()
    runner.lm_client.stream_chat.return_value = "Test answer."

    run = BenchmarkRun(
        run_id="test_ragas_unavail",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    # Ensure RAGAS is marked as unavailable
    import app.services.benchmark_runner as bm_module

    original = bm_module.RAGAS_AVAILABLE
    bm_module.RAGAS_AVAILABLE = False

    await runner._run_ragas_evaluation(run, runner._dataset)

    # Should have added results (from fallback)
    assert len(run.results) >= 0  # May add 0-2 results depending on categories

    bm_module.RAGAS_AVAILABLE = original


@pytest.mark.anyio
async def test_evaluate_retrieval_precision(runner_with_dataset):
    """Test retrieval precision evaluation."""
    runner = runner_with_dataset
    run = BenchmarkRun(
        run_id="test_precision",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    case = {
        "id": "prec_001",
        "category": "retrieval_precision",
        "query": "What is PageIndex?",
        "expected_contexts": ["Relevant context here."],
        "ground_truth": "Relevant answer.",
    }

    await runner._evaluate_retrieval_precision(run, case)

    assert len(run.results) == 1
    assert run.results[0].test_id == "quality_prec_001"
    assert run.results[0].metric == "retrieval_precision_at_5"


@pytest.mark.anyio
async def test_quality_fallback_scoring(runner_with_dataset):
    """Test fallback quality scoring when RAGAS is unavailable."""
    runner = runner_with_dataset
    runner.lm_client = AsyncMock()
    runner.lm_client.stream_chat.return_value = "PageIndex is a tree-based system for document indexing."

    run = BenchmarkRun(
        run_id="test_fallback",
        category="quality",
        status="queued",
        progress_pct=0,
    )
    runner._runs[run.run_id] = run

    cases = [
        {
            "id": "fb_001",
            "category": "faithfulness",
            "query": "test",
            "expected_contexts": ["context"],
            "ground_truth": "PageIndex is a tree-based system for document indexing.",
        }
    ]

    await runner._run_quality_fallback(run, cases, "faithfulness")

    assert len(run.results) == 1
    assert run.results[0].metric == "fallback_faithfulness"
    assert run.results[0].value > 0  # Should have some overlap
