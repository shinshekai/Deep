"""Unit tests for tool_dispatch.py — agentic dispatch loop."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tool_dispatch import run_tool_dispatch, _execute_registered_tool


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_returns_answer_on_no_tool_calls(self):
        """LLM returns content but no tool_calls → dispatch loop returns answer immediately."""
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion.return_value = {
            "content": "Paris is the capital of France.",
            "tool_calls": None,
        }

        async def ws_send(data):
            pass

        answer, transcript = await run_tool_dispatch(
            query="What is the capital of France?",
            kb_name="default",
            retrieval_pipeline="hybrid",
            lm_client=mock_lm,
            model_id="test-model",
            ws_send=ws_send,
        )

        assert "Paris" in answer
        assert not transcript  # No tools executed

    @pytest.mark.asyncio
    async def test_dispatch_executes_tool_calls(self):
        """LLM returns tool_calls → dispatch executes tools and continues."""
        call_count = [0]

        async def mock_stream(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "investigate",
                                "arguments": json.dumps({"context": "test query"}),
                            },
                        }
                    ],
                }
            return {
                "content": "Investigation complete.",
                "tool_calls": None,
            }

        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = mock_stream

        async def ws_send(data):
            pass

        answer, transcript = await run_tool_dispatch(
            query="Analyze the document.",
            kb_name="default",
            retrieval_pipeline="hybrid",
            lm_client=mock_lm,
            model_id="test-model",
            ws_send=ws_send,
        )

        assert "Investigation complete" in answer

    @pytest.mark.asyncio
    async def test_dispatch_max_rounds_guard(self):
        """Dispatch stops after MAX_DISPATCH_ROUNDS (8)."""
        call_count = [0]

        async def always_tools(**kwargs):
            call_count[0] += 1
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{call_count[0]}",
                        "type": "function",
                        "function": {
                            "name": "investigate",
                            "arguments": json.dumps({"context": "test"}),
                        },
                    }
                ],
            }

        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = always_tools

        async def ws_send(data):
            pass

        answer, transcript = await run_tool_dispatch(
            query="test",
            kb_name="default",
            retrieval_pipeline="hybrid",
            lm_client=mock_lm,
            model_id="test-model",
            ws_send=ws_send,
        )

        assert call_count[0] <= 16  # 8 dispatch + up to 8 tool executions

    @pytest.mark.asyncio
    async def test_dispatch_error_fallback(self):
        """LLM returns error → dispatch raises RuntimeError."""
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion.return_value = {"error": "model timeout"}

        async def ws_send(data):
            pass

        with pytest.raises(RuntimeError, match="model timeout"):
            await run_tool_dispatch(
                query="test",
                kb_name="default",
                retrieval_pipeline="hybrid",
                lm_client=mock_lm,
                model_id="test-model",
                ws_send=ws_send,
            )


class TestExecuteRegisteredTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await _execute_registered_tool("nonexistent_tool", {}, {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_finalize_answer_marks_complete(self):
        result = await _execute_registered_tool("finalize_answer", {}, {})
        assert "Answer complete" in result
