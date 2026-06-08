"""Retrieval route integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def create_test_app():
    """Create a minimal FastAPI test app with retrieval router."""
    from fastapi import FastAPI

    from app.routers.query import router as query_router
    from app.routers.retrieval import router as retrieval_router

    app = FastAPI()
    app.include_router(retrieval_router)
    app.include_router(query_router)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


def test_retrieve_with_tree_pipeline_returns_results(client):
    """POST /retrieve with tree pipeline returns scored results."""
    mock_tree = {
        "doc_id": "test_doc",
        "title": "Test",
        "total_pages": 5,
        "root": {
            "node_id": "root",
            "title": "Test",
            "summary": "A test document",
            "page_start": 0,
            "page_end": 4,
            "children": [],
        },
    }

    mock_ts = MagicMock()

    async def mock_search(*args, **kwargs):
        return [{"doc_id": "test_doc", "node_id": "root", "score": 0.9}]

    mock_ts.search = AsyncMock(side_effect=mock_search)

    with patch("app.routers.retrieval._load_pageindex_tree", return_value=mock_tree):
        with patch("app.routers.retrieval._get_tree_search", return_value=mock_ts):
            response = client.post(
                "/api/v1/retrieve",
                json={
                    "query": "test query",
                    "kb_name": "test_kb",
                    "retrieval_pipeline": "tree",
                    "top_k": 3,
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "tree"
    assert "results" in data
    assert "retrieval_latency_ms" in data


def test_retrieve_returns_empty_for_missing_kb(client):
    """Returns zero results for nonexistent KB."""
    response = client.post(
        "/api/v1/retrieve",
        json={
            "query": "anything",
            "kb_name": "nonexistent",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["pipeline_used"] == "tree"


def test_query_http_returns_answer(client):
    """POST /query returns structured answer with citations."""
    mock_ts = MagicMock()

    async def mock_search(*args, **kwargs):
        return [
            {
                "doc_id": "doc1",
                "page": 0,
                "section": "Doc1",
                "summary": "ML basics",
                "content": "ML is AI.",
                "node_id": "root",
            }
        ]

    mock_ts.search = mock_search

    with patch("app.routers.retrieval._load_pageindex_tree", return_value=None):
        with patch("app.routers.retrieval._list_pageindex_docs", return_value=["doc1"]):
            with patch("app.routers.retrieval._get_tree_search", return_value=mock_ts):
                with patch("app.state.lm_client") as mock_lm:
                    mock_lm.check_health = AsyncMock(return_value=True)
                    mock_lm.stream_chat = AsyncMock(
                        return_value="Machine learning is a field of AI."
                    )
                    with patch("app.state.model_manager") as mock_mm:
                        mock_mm.get_tier_from_complexity = MagicMock(return_value=1)
                        mock_mm.get_model_for_tier = AsyncMock(return_value="mock_model")
                        mock_mm.get_best_available_model = AsyncMock(return_value="mock_model")
                        with patch("app.state.vram_monitor") as mock_vm:
                            mock_vm.poll_once = AsyncMock(
                                return_value={"vram_total_mb": 1000, "vram_used_mb": 500}
                            )
                            response = client.post(
                                "/api/v1/query",
                                json={
                                    "query": "What is machine learning?",
                                    "kb_name": "test_kb",
                                    "device_id": "test-device",
                                },
                            )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "complexity_score" in data
    assert "e2e_latency_ms" in data
