import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.guided_learning import GuidedLearningService
from app.services.lm_studio_client import LMStudioClient

@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)
    
    async def mock_stream(model, messages, max_tokens):
        system_content = messages[0]["content"]
        if "LocateAgent" in system_content:
            res = ["Point 1: Intro", "Point 2: Core concepts", "Point 3: Outro"]
            return {"content": json.dumps(res)}
        elif "InteractiveAgent" in system_content:
            return {"content": "<div><h1>Interactive Lesson</h1><p>Learn this.</p></div>"}
        elif "ChatAgent" in system_content:
            return {"content": "Here is the answer to your question."}
        elif "SummaryAgent" in system_content:
            res = {"summary": "Great session.", "next_steps": ["Review"]}
            return {"content": json.dumps(res)}
            
        return {"content": "{}"}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client

@pytest.mark.asyncio
async def test_guided_learning_workflow(mock_lm_client, monkeypatch, tmp_path):
    # Mock retrieval
    mock_retrieval = AsyncMock(return_value={
        "results": [{"content": "Topic info", "doc_id": "doc1", "page": 1}]
    })
    monkeypatch.setattr("app.services.guided_learning.run_retrieval", mock_retrieval)

    # Use tmp_path for session dir
    monkeypatch.setattr("app.services.guided_learning.GuidedLearningService.__init__", lambda self, lm_client: None)
    
    service = GuidedLearningService(lm_client=mock_lm_client)
    service.lm_client = mock_lm_client
    service.sessions_dir = str(tmp_path)
    os.makedirs(service.sessions_dir, exist_ok=True)
    
    # Start Session
    session_data = await service.start_session("kb", "topic")
    session_id = session_data["session_id"]
    
    assert "learn_" in session_id
    assert len(session_data["points"]) == 3
    assert session_data["points"][0] == "Point 1: Intro"
    
    # Generate Interactive Page
    html = await service.generate_interactive_page(session_id, 0)
    assert "<h1>Interactive Lesson</h1>" in html
    
    # Chat
    answer = await service.chat(session_id, 0, "What does this mean?")
    assert answer == "Here is the answer to your question."
    
    # End Session
    summary = await service.end_session(session_id)
    assert summary["summary"] == "Great session."
    
    # Verify file saved
    session_file = os.path.join(service.sessions_dir, f"session_{session_id}.json")
    assert os.path.exists(session_file)
    with open(session_file, "r") as f:
        data = json.load(f)
        assert data["status"] == "completed"
        assert len(data["chat_history"]) == 2 # 1 user, 1 assistant
