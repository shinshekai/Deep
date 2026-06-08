"""Vector KB service tests — updated for async naive_search/hybrid_search."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

VECTOR_BASE = Path("data/knowledge_bases")


@pytest.mark.asyncio
async def test_naive_search_returns_empty_when_no_vectors():
    """Returns empty list when vector data doesn't exist."""
    from app.services.vector_kb import VectorKBService

    svc = VectorKBService(VECTOR_BASE, lm_client=None)
    result = await svc.naive_search("query", "nonexistent_kb", top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_hybrid_search_returns_empty_when_no_vectors():
    """Returns empty list when vector data doesn't exist."""
    from app.services.vector_kb import VectorKBService

    lm = MagicMock()
    lm.embed = AsyncMock(return_value=[[1.0, 0.0]])
    svc = VectorKBService(VECTOR_BASE, lm_client=lm)
    result = await svc.hybrid_search("query", "nonexistent_kb", top_k=5)
    assert result == []


def test_rrf_merge_combines_two_rankings():
    """RRF correctly merges vector and keyword results."""
    from app.services.vector_kb import _rrf_merge

    vector_results = [
        {"doc_id": "d1", "section": "A", "content": "vector match 1"},
        {"doc_id": "d2", "section": "B", "content": "vector match 2"},
        {"doc_id": "d3", "section": "C", "content": "vector match 3"},
    ]
    keyword_results = [
        {"doc_id": "d2", "section": "B", "content": "keyword match 2"},
        {"doc_id": "d4", "section": "D", "content": "keyword match 4"},
    ]

    merged = _rrf_merge(vector_results, keyword_results, top_k=5)

    # d2 appears in both, should rank highest
    assert len(merged) > 0
    top_ids = [r["doc_id"] for r in merged]
    assert top_ids[0] == "d2"


def test_keyword_search_over_text_files():
    """Keyword search finds matches in raw text files."""
    import tempfile

    from app.services.vector_kb import VectorKBService

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a text file with known content
        tmp_path = Path(tmpdir)
        (tmp_path / "doc1.txt").write_text(
            "Machine learning is a subset of artificial intelligence. "
            "Neural networks are used for deep learning applications."
        )
        (tmp_path / "doc2.txt").write_text(
            "Data science involves statistics and probability. "
            "Machine learning models require training data."
        )

        svc = VectorKBService(VECTOR_BASE)
        results = svc._keyword_search_in_directory("machine learning", tmp_path, top_k=3)

        assert len(results) > 0
        assert all("score" in r for r in results)
