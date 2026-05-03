import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.content_creation import NotebookService, CoWriterService, IdeaGenService
from app.services.lm_studio_client import LMStudioClient

@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)
    
    async def mock_stream(model, messages, max_tokens):
        user_content = messages[1]["content"]
        if "rewrite" in user_content.lower() or "expand" in user_content.lower() or "concise" in user_content.lower():
            return {"content": "Edited text."}
        elif "Annotation" in messages[0]["content"] or "annotation" in messages[0]["content"].lower():
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
    mock_retrieval = AsyncMock(return_value={
        "results": [{"content": "Topic info", "doc_id": "doc1", "page": 1, "relevance_score": 0.9}]
    })
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
