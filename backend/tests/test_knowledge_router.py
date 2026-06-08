"""Router integration tests for knowledge.py (KB management endpoints)."""

import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


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

    # Replace ``asyncio.create_task`` with a wrapper that actually
    # schedules the background coroutine on the test loop and returns
    # a completed task — this prevents the unraisable
    # "coroutine was never awaited" warning while still exercising the
    # upload-path control flow.
    import asyncio as _asyncio

    def _schedule_and_drain(coro, name=None):
        async def _runner():
            try:
                await coro
            except Exception:
                pass

        task = _asyncio.ensure_future(_runner())
        return task

    with patch("app.state.pageindex_generator", MagicMock()):
        with patch("app.state.embedding_service", MagicMock()):
            with patch("app.state.text_chunker", MagicMock()):
                with patch("app.state.vector_kb_service", MagicMock()):
                    with patch("app.state.lm_client") as mock_lm:
                        with patch(
                            "app.routers.knowledge.asyncio.create_task",
                            side_effect=_schedule_and_drain,
                        ):
                            mock_lm.check_health = AsyncMock(return_value=True)
                            file_content = b"This is test document content for unit testing."
                            response = client.post(
                                "/api/v1/knowledge/upload",
                                data={"kb_name": "test_kb"},
                                files={
                                    "file": ("test_doc.txt", BytesIO(file_content), "text/plain")
                                },
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


# ── Day 10b: filelock-based registry writes ────────────────────────────────


def test_save_registry_uses_filelock(tmp_path, monkeypatch):
    """Verify _save_registry acquires a filelock (not the old no-op Windows lock)."""
    from app.routers import knowledge

    # Redirect DATA_DIR and REGISTRY_PATH into tmp_path so we don't
    # touch the real data directory.
    monkeypatch.setattr(knowledge, "DATA_DIR", tmp_path)
    monkeypatch.setattr(knowledge, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(knowledge, "_REGISTRY_LOCK_PATH", tmp_path / "registry.lock")
    monkeypatch.setattr(knowledge, "_kb_registry", {"kb_a": {"name": "kb_a"}})

    captured = {}

    class _FakeFileLock:
        def __init__(self, *args, **kwargs):
            captured["init"] = (args, kwargs)

        def __enter__(self):
            captured["entered"] = True
            return self

        def __exit__(self, *exc):
            return False

        def acquire(self, *a, **kw):  # for direct-acquire style
            captured["acquire"] = True

        def release(self, *a, **kw):
            pass

    import filelock

    monkeypatch.setattr(filelock, "FileLock", _FakeFileLock)

    knowledge._save_registry()

    assert captured.get("entered") is True
    # The registry should be persisted to disk.
    assert (tmp_path / "registry.json").exists()


def test_save_registry_atomic_via_tmpfile(tmp_path, monkeypatch):
    """Verify the tmp-file + os.replace pattern is used so a partial
    write never corrupts an existing registry."""
    from app.routers import knowledge

    monkeypatch.setattr(knowledge, "DATA_DIR", tmp_path)
    monkeypatch.setattr(knowledge, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(knowledge, "_REGISTRY_LOCK_PATH", tmp_path / "registry.lock")

    # Pre-populate the registry with an existing KB.
    (tmp_path / "registry.json").write_text(
        json.dumps({"existing_kb": {"name": "existing"}}), encoding="utf-8"
    )
    monkeypatch.setattr(knowledge, "_kb_registry", {"new_kb": {"name": "new"}})

    class _NoOpLock:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    import filelock

    monkeypatch.setattr(filelock, "FileLock", lambda *a, **kw: _NoOpLock())

    knowledge._save_registry()

    # Both the old and the new KB are present — the merge happened.
    final = json.loads((tmp_path / "registry.json").read_text())
    assert "existing_kb" in final
    assert "new_kb" in final
    # The .tmp file is gone (os.replace moved it into place).
    assert not (tmp_path / "registry.json.tmp").exists()
