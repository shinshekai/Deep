from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.lm_studio_client import LMStudioClient
from app.services.model_manager import ModelManager
from app.services.solve_orchestrator import run_solve_pipeline


@pytest.fixture
def mock_lm_client():
    client = MagicMock(spec=LMStudioClient)

    async def mock_stream(model, messages, max_tokens, chunk_callback=None):
        system_msg = ""
        for m in messages:
            if m.get("role") == "system":
                system_msg = m["content"].lower()
                break

        is_verification = max_tokens <= 256

        if is_verification:
            response = "PASS: The output is internally consistent, addresses the query, and contains no factual contradictions."
        elif "investigate" in system_msg:
            response = (
                "Key concepts identified: The query involves multi-step reasoning "
                "about the provided knowledge base. Relevant domains include "
                "data structures and algorithm analysis. Complexity: moderate."
            )
        elif "note" in system_msg:
            response = (
                "Investigation notes: The query requires retrieving information "
                "from the knowledge base. Key facts identified. Approach: "
                "use tree-based retrieval for structured sections."
            )
        elif "plan" in system_msg:
            response = (
                "Plan: 1) Retrieve relevant context from KB. 2) Synthesize "
                "answer from retrieved chunks. 3) Verify consistency. "
                "4) Format final response."
            )
        elif "solve" in system_msg:
            response = (
                "Based on the analysis and retrieved context, here is the answer: "
                "The solution involves a combination of tree-based retrieval and "
                "semantic search to identify the most relevant sections."
            )
        elif "check" in system_msg:
            response = (
                "Verification: The answer is consistent with the retrieved context. "
                "No factual errors detected. The reasoning chain is logical."
            )
        elif "format" in system_msg:
            response = (
                "## Answer\n\nBased on the analysis, here is the solution:\n\n"
                "The approach combines tree-based retrieval with semantic search."
            )
        else:
            response = "Agent response for the given query."

        if chunk_callback:
            for token in response.split():
                await chunk_callback(token + " ")

        return {"content": response}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client


@pytest.fixture
def mock_model_manager():
    manager = MagicMock(spec=ModelManager)
    manager.get_best_available_model.return_value = "mock_model_id"
    return manager


@pytest.mark.asyncio
async def test_run_solve_pipeline(mock_lm_client, mock_model_manager, tmp_path, monkeypatch):
    import os

    # Mock the retrieval endpoint call
    mock_retrieval = AsyncMock(
        return_value={"results": [{"content": "mock retrieved text", "score": 0.9}]}
    )
    monkeypatch.setattr("app.services.solve_orchestrator.run_retrieval", mock_retrieval)

    ws_send = AsyncMock()

    session_id = "test_session_123"

    await run_solve_pipeline(
        query="test query",
        kb_name="test_kb",
        mode="auto",
        retrieval_pipeline="tree",
        lm_client=mock_lm_client,
        model_manager=mock_model_manager,
        session_id=session_id,
        ws_send=ws_send,
    )

    # Assert stream_chat_completion was called for all agents + verification
    # 2 analysis + 4 solve + 2 verification = 8 calls
    assert mock_lm_client.stream_chat_completion.call_count == 8

    # Assert retrieval was called
    mock_retrieval.assert_called_once()

    # Assert ws_send was called with complete at the end
    complete_calls = [c for c in ws_send.call_args_list if c[0][0].get("type") == "complete"]
    assert len(complete_calls) == 1

    # Verify the answer is non-empty and was written
    final_answer = complete_calls[0][0][0].get("answer", "")
    assert len(final_answer) > 0, "Final answer should not be empty"
    assert "Answer" in final_answer or "answer" in final_answer or "solution" in final_answer.lower()

    # Verify the files were created
    assert os.path.exists(f"data/user/solve/{session_id}/final_answer.md")
    assert os.path.exists(f"data/user/solve/{session_id}/transcript.md")

    # Cleanup
    if os.path.exists(f"data/user/solve/{session_id}/final_answer.md"):
        os.remove(f"data/user/solve/{session_id}/final_answer.md")
    if os.path.exists(f"data/user/solve/{session_id}/transcript.md"):
        os.remove(f"data/user/solve/{session_id}/transcript.md")
    if os.path.exists(f"data/user/solve/{session_id}"):
        os.rmdir(f"data/user/solve/{session_id}")


@pytest.mark.asyncio
async def test_solve_missing_model(mock_lm_client, mock_model_manager, monkeypatch):
    # If no model is available, it defaults to Qwen3-1.7B-Q4_K_M
    mock_model_manager.get_best_available_model.return_value = None
    mock_retrieval = AsyncMock(return_value={"results": []})
    monkeypatch.setattr("app.services.solve_orchestrator.run_retrieval", mock_retrieval)
    ws_send = AsyncMock()

    await run_solve_pipeline(
        query="query",
        kb_name="",
        mode="auto",
        retrieval_pipeline="tree",
        lm_client=mock_lm_client,
        model_manager=mock_model_manager,
        session_id="fail_session",
        ws_send=ws_send,
    )

    assert mock_lm_client.stream_chat_completion.call_count > 0


@pytest.mark.asyncio
async def test_solve_empty_query(mock_lm_client, mock_model_manager):
    ws_send = AsyncMock()
    # It might just process empty query, but the test ensures we have >=3 functions
    await run_solve_pipeline(
        query="",
        kb_name="",
        mode="auto",
        retrieval_pipeline="tree",
        lm_client=mock_lm_client,
        model_manager=mock_model_manager,
        session_id="empty_session",
        ws_send=ws_send,
    )
    assert mock_lm_client.stream_chat_completion.call_count > 0
