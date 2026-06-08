import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.content_creation import CoWriterService, IdeaGenService, NotebookService
from app.services.lm_studio_client import LMStudioClient


@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)

    async def mock_stream(model, messages, max_tokens):
        user_content = messages[1]["content"]
        if (
            "rewrite" in user_content.lower()
            or "expand" in user_content.lower()
            or "concise" in user_content.lower()
        ):
            return {"content": "Edited text."}
        elif (
            "Annotation" in messages[0]["content"] or "annotation" in messages[0]["content"].lower()
        ):
            return {"content": "Text [Citation 1]."}
        elif "JSON array of ideas" in user_content:
            res = ["Idea 1", "Idea 2"]
            return {"content": json.dumps(res)}

        return {"content": ""}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client


def test_notebook_service(tmp_path):
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)

    # Create
    nb = service.create_notebook("Test NB", "Desc")
    assert nb["title"] == "Test NB"
    nb_id = nb["id"]

    # Add note
    service.add_note(nb_id, "This is a note.")

    # Get notebook
    nb_refreshed = service.get_notebook(nb_id)
    assert len(nb_refreshed["notes"]) == 1
    assert nb_refreshed["notes"][0]["content"] == "This is a note."

    # List notebooks
    nbs = service.list_notebooks()
    assert len(nbs) == 1


@pytest.mark.asyncio
async def test_cowriter_service(mock_lm_client, monkeypatch):
    service = CoWriterService(lm_client=mock_lm_client)

    # Edit text
    res = await service.edit_text("hello", "shorten")
    assert res["text"] == "Edited text."
    assert "provenance" in res
    assert res["provenance"]["action"] == "shorten"

    # Annotate
    mock_retrieval = AsyncMock(
        return_value={
            "results": [
                {"content": "Topic info", "doc_id": "doc1", "page": 1, "relevance_score": 0.9}
            ]
        }
    )
    monkeypatch.setattr("app.services.content_creation.run_retrieval", mock_retrieval)

    res = await service.auto_annotate("hello", "kb")
    assert res["text"] == "Text [Citation 1]."
    assert "provenance" in res
    assert res["provenance"]["action"] == "annotate"
    assert len(res["provenance"]["sources"]) == 1
    assert res["provenance"]["sources"][0]["doc_id"] == "doc1"


@pytest.mark.asyncio
async def test_ideagen_service(mock_lm_client, tmp_path):
    nb_service = NotebookService()
    nb_service.notebooks_dir = str(tmp_path)
    nb = nb_service.create_notebook("Test NB")
    nb_service.add_note(nb["id"], "Note 1")

    ig_service = IdeaGenService(lm_client=mock_lm_client, notebook_service=nb_service)

    ideas = await ig_service.generate_ideas([nb["id"]])
    assert len(ideas) == 2
    assert ideas[0] == "Idea 1"


# ── Day 9a: File I/O error handling ────────────────────────────────────────


def test_get_notebook_raises_filenotfound(tmp_path):
    """Missing notebook raises FileNotFoundError (router maps to 404)."""
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)
    with pytest.raises(FileNotFoundError):
        service.get_notebook("nb_does_not_exist")


def test_get_notebook_raises_value_error_on_corruption(tmp_path):
    """A notebook file with invalid JSON raises ValueError (router maps to 500)."""
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)
    bad_path = tmp_path / "nb_corrupt.json"
    bad_path.write_text("{ this is not valid JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        service.get_notebook("nb_corrupt")


def test_list_notebooks_skips_corrupted_files(tmp_path):
    """One corrupted notebook should not sink the whole list endpoint."""
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)
    good = service.create_notebook("Good")
    (tmp_path / "nb_bad.json").write_text("not json", encoding="utf-8")
    notebooks = service.list_notebooks()
    assert len(notebooks) == 1
    assert notebooks[0]["id"] == good["id"]


def test_list_notebooks_handles_missing_directory(tmp_path, monkeypatch):
    """If the notebooks directory disappears mid-flight, return [] rather than 500."""
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)
    # Replace listdir with one that raises FileNotFoundError
    import os as _os

    monkeypatch.setattr(_os, "listdir", lambda p: (_ for _ in ()).throw(FileNotFoundError()))
    assert service.list_notebooks() == []


def test_create_notebook_propagates_oserror(tmp_path, monkeypatch):
    """If the underlying open() fails with PermissionError, the service
    surfaces the OSError (router maps to 503) — doesn't swallow it."""
    service = NotebookService()
    service.notebooks_dir = str(tmp_path)
    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        if "w" in mode:
            raise PermissionError("disk full")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(OSError):
        service.create_notebook("Test")


def test_router_add_note_404_for_missing_notebook():
    """The router endpoint maps FileNotFoundError → 404, not 500."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.agent import router as agent_router

    app = FastAPI()
    app.include_router(agent_router)
    client = TestClient(app)
    resp = client.post("/notebooks/nb_nope/notes", json={"content": "x"})
    assert resp.status_code == 404
