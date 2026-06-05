"""Tests for extracted WebSocket handlers (app.websocket_handlers)."""

import pytest
import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

from app.websocket_handlers import (
    _run_solve_pipeline_for_message,
    _watch_ws_disconnect,
    ws_solve,
    ws_metrics,
    broadcast_loop,
    ttl_loop,
)


def test_run_solve_pipeline_for_message_signature():
    sig = inspect.signature(_run_solve_pipeline_for_message)
    assert list(sig.parameters) == ["ws", "data", "state"]


def test_run_solve_pipeline_for_message_exportable_from_main():
    from app import main as app_main
    assert hasattr(app_main, "_run_solve_pipeline_for_message")
    assert callable(app_main._run_solve_pipeline_for_message)


def test_ws_solve_importable():
    assert callable(ws_solve)


def test_ws_metrics_importable():
    assert callable(ws_metrics)


def test_broadcast_loop_importable():
    assert inspect.iscoroutinefunction(broadcast_loop)


def test_ttl_loop_importable():
    assert inspect.iscoroutinefunction(ttl_loop)


def test_ttl_loop_has_last_cleanup_attr():
    assert hasattr(ttl_loop, "_last_cleanup")
    assert isinstance(ttl_loop._last_cleanup, float)


def test_ws_handlers_source_contains_solve_handler():
    source = inspect.getsource(ws_solve)
    assert "ws_auth_token" in source
    assert "WebSocketDisconnect" in source


def test_ws_handlers_source_contains_metrics_handler():
    source = inspect.getsource(ws_metrics)
    assert "ws_auth_token" in source
    assert "ACTIVE_WS_CONNECTIONS" in source


def test_ws_handlers_source_has_auth_check():
    source = inspect.getsource(ws_solve)
    assert "safe_compare" in source
    assert "Unauthorized" in source


def test_ws_handlers_module_has_metrics_history():
    from app.websocket_handlers import _metrics_history
    assert isinstance(_metrics_history, list)


@pytest.mark.asyncio
async def test_empty_query_sends_error():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    await _run_solve_pipeline_for_message(ws, {"query": ""}, MagicMock())
    ws.send_json.assert_called_once()
    frame = ws.send_json.call_args[0][0]
    assert frame["type"] == "error"
    assert frame["error"] == "empty_query"


@pytest.mark.asyncio
async def test_whitespace_query_sends_error():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    await _run_solve_pipeline_for_message(ws, {"query": "   "}, MagicMock())
    frame = ws.send_json.call_args[0][0]
    assert frame["error"] == "empty_query"


@pytest.mark.asyncio
async def test_lm_down_fallback():
    from unittest.mock import patch
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    mock_state = MagicMock()
    mock_state.lm_client.check_health = AsyncMock(return_value=False)

    with patch("app.websocket_handlers.asyncio.sleep", new_callable=AsyncMock):
        await _run_solve_pipeline_for_message(
            ws, {"query": "hello world", "mode": "auto"}, mock_state
        )

    calls = ws.send_json.call_args_list
    types = [c[0][0]["type"] for c in calls]
    assert "agent_step" in types
    assert "complete" in types
    complete = [c[0][0] for c in calls if c[0][0]["type"] == "complete"][0]
    assert "answer" in complete
    assert "session_id" in complete
