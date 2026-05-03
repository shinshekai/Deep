"""Router integration tests for agent.py (FR-4 to FR-7 endpoints)."""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


def create_test_app():
    """Create a minimal FastAPI test app with agent router."""
    from fastapi import FastAPI
    from app.routers.agent import router as agent_router

    app = FastAPI()
    app.include_router(agent_router)
    return app


# ── Research endpoints ───────────────────────────────────────────────────────

def test_start_research():
    """Test POST /api/v1/research starts a session."""
    app = create_test_app()
    client = TestClient(app)

    mock_dr = MagicMock()
    mock_dr.start_research = AsyncMock(return_value="session_123")

    with patch("app.routers.agent.deep_research_service", mock_dr):
        response = client.post("/api/v1/research", json={
            "kb_name": "test_kb",
            "query": "What is machine learning?",
            "mode": "parallel",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session_123"
    assert data["status"] == "RESEARCHING"


def test_get_research_status():
    """Test GET /api/v1/research/{session_id} returns session status."""
    app = create_test_app()
    client = TestClient(app)

    mock_dr = MagicMock()
    mock_dr.get_status = MagicMock(return_value={
        "status": "COMPLETED",
        "final_report": "Research complete."
    })

    with patch("app.routers.agent.deep_research_service", mock_dr):
        response = client.get("/api/v1/research/session_123")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"


def test_get_research_status_not_found():
    """Test 404 for missing research session."""
    app = create_test_app()
    client = TestClient(app)

    mock_dr = MagicMock()
    mock_dr.get_status = MagicMock(side_effect=ValueError("not found"))

    with patch("app.routers.agent.deep_research_service", mock_dr):
        response = client.get("/api/v1/research/nonexistent")

    assert response.status_code == 404


# ── Question generation endpoint ─────────────────────────────────────────────

def test_generate_questions():
    """Test POST /api/v1/questions/generate."""
    app = create_test_app()
    client = TestClient(app)

    with patch("app.routers.agent.lm_client") as mock_lm:
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": '["Q1?", "Q2?", "Q3?"]'
        })
        mock_lm.check_health = AsyncMock(return_value=True)
        with patch("app.state.lm_client", mock_lm):
            response = client.post("/api/v1/questions/generate", json={
                "kb_name": "test_kb",
                "topic": "AI basics",
            })

    assert response.status_code == 200


# ── Notebook CRUD endpoints ─────────────────────────────────────────────────

def test_notebook_crud():
    """Test POST /api/v1/notebooks and GET /api/v1/notebooks."""
    app = create_test_app()
    client = TestClient(app)
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(
            __import__("app.services.content_creation", fromlist=["NotebookService"]).NotebookService,
            "__init__",
            lambda self: setattr(self, "notebooks_dir", tmpdir) or None
        ):
            # Create notebook
            response = client.post("/api/v1/notebooks", json={
                "title": "Test Notebook",
                "description": "A test"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Test Notebook"
            nb_id = data["id"]

            # List notebooks
            response = client.get("/api/v1/notebooks")
            assert response.status_code == 200
            nbs = response.json()
            assert len(nbs) >= 1

            # Add note
            response = client.post(f"/api/v1/notebooks/{nb_id}/notes", json={
                "content": "Important note"
            })
            assert response.status_code == 200
            note = response.json()
            assert note["content"] == "Important note"


# ── CoWriter endpoints ───────────────────────────────────────────────────────

def test_cowriter_edit():
    """Test POST /api/v1/cowriter/edit returns provenance."""
    app = create_test_app()
    client = TestClient(app)

    with patch("app.routers.agent.lm_client") as mock_lm:
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": "Shortened version."
        })

        response = client.post("/api/v1/cowriter/edit", json={
            "text": "This is a very long text that needs shortening.",
            "action": "shorten",
        })

    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "provenance" in data
    assert data["provenance"]["action"] == "shorten"
