"""End-to-end tests for critical user flows (upload → query → response).

Uses httpx.AsyncClient with ASGITransport to exercise the full FastAPI
stack without starting a real server.  All state.* services are mocked by
the autouse ``mock_state`` fixture in conftest.py.
"""

import asyncio
import io
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app import state


# ── Helpers ──────────────────────────────────────────────────────────────────

transport = httpx.ASGITransport(app=app)


def _mock_task(coro):
    """Return a completed mock Task so ``asyncio.create_task`` patches
    don't leave unawaited coroutines."""
    # Consume the coroutine to suppress the RuntimeWarning
    coro.close()
    mock = MagicMock(spec=asyncio.Task)
    mock.done.return_value = True
    return mock


async def _get_client(**kwargs):
    return httpx.AsyncClient(transport=transport, base_url="http://testserver", **kwargs)


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check():
    """GET /api/v1/health returns 200 with expected fields."""
    async with await _get_client() as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "lm_studio" in body
    assert "gpu" in body
    assert "uptime_seconds" in body


@pytest.mark.asyncio
async def test_create_knowledge_base():
    """POST /api/v1/knowledge/bases creates a new KB."""
    async with await _get_client() as client:
        resp = await client.post(
            "/api/v1/knowledge/bases",
            data={"kb_name": "e2e_test_kb"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "e2e_test_kb"
    assert body["status"] == "active"
    assert "created_at" in body

    # Cleanup
    from app.routers.knowledge import DATA_DIR
    import shutil
    kb_path = DATA_DIR / "e2e_test_kb"
    if kb_path.exists():
        shutil.rmtree(kb_path)


@pytest.mark.asyncio
async def test_list_knowledge_bases():
    """GET /api/v1/knowledge/bases returns a list."""
    async with await _get_client() as client:
        resp = await client.get("/api/v1/knowledge/bases")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    # At minimum the "default" KB created at module import exists
    names = [kb["name"] for kb in body]
    assert "default" in names


@pytest.mark.asyncio
async def test_upload_document_flow():
    """POST /api/v1/knowledge/upload accepts a document and returns a task_id."""
    file_content = b"Unit test document for e2e upload flow."

    # Stub out background processing so no real LLM/IO work happens
    with patch("app.routers.knowledge.asyncio.create_task", side_effect=_mock_task):
        async with await _get_client() as client:
            resp = await client.post(
                "/api/v1/knowledge/upload",
                data={"kb_name": "default"},
                files={"file": ("test_doc.txt", io.BytesIO(file_content), "text/plain")},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "task_id" in body
    assert body["status"] == "processing"
    assert body["doc_id"] == "test_doc.txt"


@pytest.mark.asyncio
async def test_query_flow():
    """POST /api/v1/query returns a structured QueryResponse."""
    # Mock retrieval to return empty results (no real vector store)
    with patch("app.routers.retrieval.retrieve", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = {"results": [], "pipeline_used": "tree"}

        async with await _get_client() as client:
            resp = await client.post(
                "/api/v1/query",
                json={
                    "query": "What is this document about?",
                    "kb_name": "default",
                    "mode": "auto",
                    "retrieval_pipeline": "tree",
                },
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert "citations" in body
    assert isinstance(body["citations"], list)
    assert "model_tier_used" in body
    assert "e2e_latency_ms" in body
    assert body["e2e_latency_ms"] >= 0


@pytest.mark.asyncio
async def test_full_lifecycle():
    """Create KB → upload doc → query → delete KB (happy path)."""
    kb_name = "e2e_lifecycle_kb"
    file_content = b"Lifecycle test document content."

    async with await _get_client() as client:
        # 1. Create knowledge base
        resp = await client.post(
            "/api/v1/knowledge/bases",
            data={"kb_name": kb_name},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == kb_name

        # 2. Upload a document
        with patch("app.routers.knowledge.asyncio.create_task", side_effect=_mock_task):
            resp = await client.post(
                "/api/v1/knowledge/upload",
                data={"kb_name": kb_name},
                files={"file": ("lifecycle.txt", io.BytesIO(file_content), "text/plain")},
            )
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        assert task_id

        # 3. Query the knowledge base
        with patch("app.routers.retrieval.retrieve", new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = {"results": [], "pipeline_used": "tree"}
            resp = await client.post(
                "/api/v1/query",
                json={
                    "query": "Summarize the uploaded document.",
                    "kb_name": kb_name,
                },
            )
        assert resp.status_code == 200
        assert "answer" in resp.json()

        # 4. Delete the knowledge base
        resp = await client.delete(f"/api/v1/knowledge/bases/{kb_name}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert resp.json()["kb_name"] == kb_name

        # 5. Verify deletion — get endpoint returns inactive stub
        resp = await client.get(f"/api/v1/knowledge/bases/{kb_name}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "inactive" or body.get("total_docs", 0) == 0
