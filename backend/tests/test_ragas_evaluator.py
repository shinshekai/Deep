"""RAGAS evaluator tests."""

import pytest


@pytest.fixture
def sample_data():
    return {
        "question": "What is deep learning?",
        "answer": "Deep learning is a subset of machine learning based on neural networks.",
        "contexts": ["Deep learning uses neural networks with multiple layers."],
        "ground_truth": "Deep learning is ML with neural networks.",
    }


def test_ragas_evaluator_creation(sample_data):
    """RAGASEvaluator can be created."""
    from app.services.ragas_evaluator import RAGASEvaluator
    evaluator = RAGASEvaluator()
    assert evaluator is not None


@pytest.mark.asyncio
async def test_compute_faithfulness(sample_data):
    """Computes faithfulness score."""
    from app.services.ragas_evaluator import RAGASEvaluator
    evaluator = RAGASEvaluator()

    score = await evaluator.compute_faithfulness(
        question=sample_data["question"],
        answer=sample_data["answer"],
        contexts=sample_data["contexts"],
    )
    if score is not None:
        assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_compute_all_metrics(sample_data):
    """Computes all RAGAS metrics."""
    from app.services.ragas_evaluator import RAGASEvaluator
    evaluator = RAGASEvaluator()

    if not evaluator.is_available:
        pytest.skip("ragas not installed")

    metrics = await evaluator.evaluate_sample(
        question=sample_data["question"],
        answer=sample_data["answer"],
        contexts=sample_data["contexts"],
        ground_truth=sample_data["ground_truth"],
    )
    assert "faithfulness" in metrics
    assert "answer_relevancy" in metrics
    assert "context_precision" in metrics
    assert "context_recall" in metrics
