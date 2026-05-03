"""Router integration tests for knowledge.py (KB management endpoints)."""

import pytest
import json
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO


def create_test_app():
    """Create a minimal FastAPI test app with knowledge router."""
    from fastapi import FastAPI
    from app.routers.knowledge import router as knowledge_router
    app = FastAPI()
    app.include_router(knowledge_router)
    return app


def test_list_knowledge_bases():
    """Test GET /api/v1/knowledge/bases returns KB list."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/api/v1/knowledge/bases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_kb_status():
    """Test GET /api/v1/knowledge/bases/{kb_name}."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/api/v1/knowledge/bases/nonexistent_kb")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data or "name" in data or isinstance(data, dict)


def test_upload_document():
    """Test POST /api/v1/knowledge/upload processes a txt file."""
    app = create_test_app()
    client = TestClient(app)

    with patch("app.state.pageindex_generator", MagicMock()):
        with patch("app.state.embedding_service", MagicMock()):
            with patch("app.state.text_chunker", MagicMock()):
                with patch("app.state.vector_kb_service", MagicMock()):
                    with patch("app.state.lm_client") as mock_lm:
                        with patch("app.routers.knowledge.asyncio.create_task", MagicMock()):
                            mock_lm.check_health = AsyncMock(return_value=True)
                            file_content = b"This is test document content for unit testing."
                            response = client.post(
                                "/api/v1/knowledge/upload",
                                data={"kb_name": "test_kb"},
                                files={"file": ("test_doc.txt", BytesIO(file_content), "text/plain")},
                            )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data


def test_processing_status_not_found():
    """Test GET /api/v1/knowledge/tasks/{task_id} for unknown task."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/api/v1/knowledge/tasks/nonexistent_task")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unknown"


def test_delete_document():
    """Test DELETE /api/v1/knowledge/bases/{kb_name}/documents/{doc_id}."""
    app = create_test_app()
    client = TestClient(app)

    response = client.delete("/api/v1/knowledge/bases/test_kb/documents/nonexistent_doc")
    # Our endpoint returns 404 if the document tree isn't found
    assert response.status_code == 404
