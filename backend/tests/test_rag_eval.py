"""RAG evaluation service tests."""

import pytest


@pytest.fixture
def sample_data():
    return {
        "question": "What is deep learning?",
        "answer": "Deep learning is a subset of machine learning based on neural networks.",
        "contexts": ["Deep learning uses neural networks with multiple layers."],
        "ground_truth": "Deep learning is ML with neural networks.",
    }


def test_rag_evaluator_creation():
    from app.services.rag_eval import RAGEvaluator
    evaluator = RAGEvaluator()
    assert evaluator is not None
    assert evaluator.is_available is True


def test_faithfulness_basic(sample_data):
    from app.services.rag_eval import faithfulness
    score = faithfulness(sample_data["answer"], sample_data["contexts"])
    assert 0.0 <= score <= 1.0
    assert score > 0.0


def test_faithfulness_empty():
    from app.services.rag_eval import faithfulness
    assert faithfulness("", ["ctx"]) == 0.0
    assert faithfulness("ans", []) == 0.0


def test_answer_relevancy_basic(sample_data):
    from app.services.rag_eval import answer_relevancy
    score = answer_relevancy(sample_data["question"], sample_data["answer"])
    assert 0.0 <= score <= 1.0
    assert score > 0.0


def test_answer_relevancy_empty():
    from app.services.rag_eval import answer_relevancy
    assert answer_relevancy("", "ans") == 0.0
    assert answer_relevancy("q", "") == 0.0


def test_context_precision_basic(sample_data):
    from app.services.rag_eval import context_precision
    score = context_precision(sample_data["contexts"], sample_data["ground_truth"])
    assert 0.0 <= score <= 1.0


def test_context_recall_basic(sample_data):
    from app.services.rag_eval import context_recall
    score = context_recall(sample_data["contexts"], sample_data["ground_truth"])
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_evaluate_sample(sample_data):
    from app.services.rag_eval import RAGEvaluator
    evaluator = RAGEvaluator()
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
    for v in metrics.values():
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_compute_faithfulness(sample_data):
    from app.services.rag_eval import RAGEvaluator
    evaluator = RAGEvaluator()
    score = await evaluator.compute_faithfulness(
        question=sample_data["question"],
        answer=sample_data["answer"],
        contexts=sample_data["contexts"],
    )
    assert 0.0 <= score <= 1.0
