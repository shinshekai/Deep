import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.question_generator import QuestionGenService
from app.services.lm_studio_client import LMStudioClient

@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)
    
    async def mock_stream(model, messages, max_tokens):
        system_content = messages[0]["content"]
        if "Generator Agent" in system_content:
            # Return valid JSON array
            res = [
                {
                    "id": "q1",
                    "text": "What is 2+2?",
                    "type": "multiple_choice",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": "4",
                    "explanation": "Math."
                }
            ]
            return {"content": json.dumps(res)}
        elif "Validator Agent" in system_content:
            # Just pass it back
            res = [
                {
                    "id": "q1",
                    "text": "What is 2+2?",
                    "type": "multiple_choice",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": "4",
                    "explanation": "Math."
                }
            ]
            return {"content": f"```json\n{json.dumps(res)}\n```"}
        return {"content": "[]"}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client


@pytest.mark.asyncio
async def test_question_generator(mock_lm_client, monkeypatch):
    # Mock retrieval
    mock_retrieval = AsyncMock(return_value={
        "results": [{"content": "2+2 equals 4. Math is fun.", "doc_id": "math_book", "page": 1}]
    })
    monkeypatch.setattr("app.services.question_generator.run_retrieval", mock_retrieval)

    service = QuestionGenService(lm_client=mock_lm_client)
    
    questions = await service.generate_questions(
        kb_name="test_kb",
        topic="Math",
        count=1,
        difficulty="easy",
        question_type="multiple_choice"
    )
    
    assert len(questions) == 1
    assert questions[0]["id"] == "q1"
    assert questions[0]["correct_answer"] == "4"
    
    # 2 calls: one for drafting, one for validation
    assert mock_lm_client.stream_chat_completion.call_count == 2
    mock_retrieval.assert_called_once()
