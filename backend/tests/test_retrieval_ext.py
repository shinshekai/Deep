"""Extended tests for retrieval router pipelines."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.routers.retrieval import router


def create_test_app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


def test_retrieve_naive_pipeline(client):
    """Test naive vector retrieval."""
    mock_vkb = MagicMock()
    mock_vkb.naive_search = AsyncMock(return_value=[{"doc_id": "test1", "score": 0.8}])

    with patch("app.routers.retrieval._list_pageindex_docs", return_value=["test1"]):
        with patch("app.routers.retrieval._get_vector_kb", return_value=mock_vkb):
            with patch("app.services.query_router.route_query", return_value="naive"):
                response = client.post(
                    "/api/v1/retrieve",
                    json={
                        "query": "test query",
                        "kb_name": "test_kb",
                        "retrieval_pipeline": "naive",
                    },
                )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "naive"
    assert len(data["results"]) == 1


def test_retrieve_hybrid_pipeline(client):
    """Test hybrid retrieval."""
    mock_vkb = MagicMock()
    mock_vkb.hybrid_search = AsyncMock(return_value=[{"doc_id": "test1", "score": 0.9}])

    with patch("app.routers.retrieval._list_pageindex_docs", return_value=["test1"]):
        with patch("app.routers.retrieval._get_vector_kb", return_value=mock_vkb):
            with patch("app.services.query_router.route_query", return_value="hybrid"):
                response = client.post(
                    "/api/v1/retrieve",
                    json={
                        "query": "test query",
                        "kb_name": "test_kb",
                        "retrieval_pipeline": "hybrid",
                    },
                )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "hybrid"


def test_retrieve_combined_pipeline(client):
    """Test combined tree + naive retrieval."""
    mock_tree = MagicMock()
    mock_tree.search = AsyncMock(return_value=[{"doc_id": "test1", "section": "A", "score": 0.9}])

    mock_vkb = MagicMock()
    mock_vkb.naive_search = AsyncMock(
        return_value=[{"doc_id": "test2", "section": "B", "score": 0.8}]
    )

    with patch("app.routers.retrieval._list_pageindex_docs", return_value=["test1", "test2"]):
        with patch("app.routers.retrieval._get_tree_search", return_value=mock_tree):
            with patch("app.routers.retrieval._get_vector_kb", return_value=mock_vkb):
                with patch("app.services.query_router.route_query", return_value="combined"):
                    response = client.post(
                        "/api/v1/retrieve",
                        json={
                            "query": "test query",
                            "kb_name": "test_kb",
                            "retrieval_pipeline": "combined",
                        },
                    )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "combined"
    assert len(data["results"]) == 2


def test_retrieve_ara_pipeline(client):
    """Test ARA pipeline retrieval."""
    mock_compiler = MagicMock()
    mock_artifact = MagicMock()
    mock_compiler.load = MagicMock(return_value=mock_artifact)

    # Mock search claims to return one claim
    mock_claim = MagicMock()
    mock_claim.statement = "Matched claim"
    mock_claim.evidence_refs = []
    mock_claim.claim_id = "C1"
    mock_compiler.search_claims = MagicMock(return_value=[mock_claim])
    mock_compiler.search_heuristics = MagicMock(return_value=[])

    with patch("app.routers.retrieval._list_pageindex_docs", return_value=["test1"]):
        with patch("app.services.ara_compiler.ARACompiler", return_value=mock_compiler):
            # We need to mock DATA_DIR existing and having ARA dirs
            with patch("app.routers.retrieval.DATA_DIR") as mock_dir:
                with patch("app.services.query_router.route_query", return_value="ara"):
                    mock_ara_dir = MagicMock()
                    mock_ara_dir.exists.return_value = True
                    mock_doc_path = MagicMock()
                    mock_doc_path.is_dir.return_value = True
                    mock_doc_path.name = "test1"
                    mock_ara_dir.iterdir.return_value = [mock_doc_path]
                    mock_dir.__truediv__.return_value.__truediv__.return_value = mock_ara_dir

                    response = client.post(
                        "/api/v1/retrieve",
                        json={
                            "query": "test query",
                            "kb_name": "test_kb",
                            "retrieval_pipeline": "ara",
                        },
                    )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "ara"
    assert len(data["results"]) == 1
    assert data["results"][0]["content"] == "Matched claim"
    assert data["results"][0]["type"] == "claim"


def test_retrieve_graph_pipeline(client):
    """Test graph pipeline retrieval fallback."""
    with patch("app.routers.retrieval._list_pageindex_docs", return_value=["test1"]):
        with patch("app.services.query_router.route_query", return_value="graph"):
            response = client.post(
                "/api/v1/retrieve",
                json={
                    "query": "test query",
                    "kb_name": "test_kb",
                    "retrieval_pipeline": "graph",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "graph"
    # Fallback usually returns [] if no real graph impl
    assert isinstance(data["results"], list)
