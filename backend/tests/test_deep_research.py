import pytest
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.deep_research import DeepResearchService
from app.services.lm_studio_client import LMStudioClient

@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)
    
    async def mock_stream(model, messages, max_tokens):
        system_content = messages[0]["content"]
        if "DecomposeAgent" in system_content:
            res = ["Subtopic 1", "Subtopic 2"]
            return {"content": json.dumps(res)}
        elif "NoteAgent" in system_content:
            # Simulate a slight delay to allow parallel execution test
            await asyncio.sleep(0.01)
            return {"content": "Here are the notes."}
        elif "ReportAgent" in system_content:
            return {"content": "# Final Report\n\nNotes."}
            
        return {"content": ""}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client

@pytest.mark.asyncio
async def test_deep_research_workflow(mock_lm_client, monkeypatch, tmp_path):
    # Mock retrieval
    mock_retrieval = AsyncMock(return_value={
        "results": [{"content": "Topic info", "doc_id": "doc1", "page": 1}]
    })
    monkeypatch.setattr("app.services.deep_research.run_retrieval", mock_retrieval)

    # Prevent asyncio.create_task from leaking if we don't await it
    # We will await it manually
    
    service = DeepResearchService(lm_client=mock_lm_client)
    service.sessions_dir = str(tmp_path)
    os.makedirs(service.sessions_dir, exist_ok=True)
    
    # 1. Start Research
    session_id = await service.start_research("test_kb", "query", mode="parallel")
    
    assert "research_" in session_id
    
    # Verify initial state
    data = service.get_status(session_id)
    assert data["status"] == "RESEARCHING"
    assert len(data["queue"]) == 2
    assert data["queue"][0]["query"] == "Subtopic 1"
    assert data["queue"][0]["status"] == "PENDING"
    
    # 2. Process Queue manually (since start_research kicked it off in bg, we wait for all active_tasks)
    # Actually, start_research created a task in service.active_tasks. Let's await it.
    assert len(service.active_tasks) == 1
    task = list(service.active_tasks)[0]
    await task
    
    # 3. Verify final state
    data = service.get_status(session_id)
    assert data["status"] == "COMPLETED"
    assert data["final_report"] == "# Final Report\n\nNotes."
    assert data["queue"][0]["status"] == "COMPLETED"
    assert data["queue"][0]["notes"] == "Here are the notes."
    
    # Assert call counts
    # 1 for Decompose, 2 for NoteAgent (since 2 subtopics), 1 for Report
    assert mock_lm_client.stream_chat_completion.call_count == 4
    # 2 calls to retrieval (one per subtopic)
    assert mock_retrieval.call_count == 2

@pytest.mark.asyncio
async def test_deep_research_invalid_session(mock_lm_client, tmp_path):
    service = DeepResearchService(lm_client=mock_lm_client)
    service.sessions_dir = str(tmp_path)
    with pytest.raises(Exception):
        service.get_status("does_not_exist")

@pytest.mark.asyncio
async def test_deep_research_empty_query(mock_lm_client, tmp_path, monkeypatch):
    service = DeepResearchService(lm_client=mock_lm_client)
    service.sessions_dir = str(tmp_path)
    
    mock_retrieval = AsyncMock(return_value={"results": []})
    monkeypatch.setattr("app.services.deep_research.run_retrieval", mock_retrieval)
    
    session_id = await service.start_research("test_kb", "")
    assert session_id
    # We await the active task
    if service.active_tasks:
        await list(service.active_tasks)[0]
        
    data = service.get_status(session_id)
    assert data["status"] == "COMPLETED"
