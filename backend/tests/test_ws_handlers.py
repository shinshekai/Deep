"""WebSocket handler tests — async tests using websockets.connect.

Covers the two WS endpoints defined in app.main:
  /ws/metrics  — metrics broadcast
  /api/v1/solve — Smart Solve dual-loop
"""

import asyncio
import json

import pytest
import uvicorn
import websockets

from app.config import get_settings


@pytest.fixture
async def ws_server():
    """Start the FastAPI app on a high port and yield the base WS URL.

    The lifespan initialises real services (VRAMMonitor, LMStudioClient,
    etc.) which gracefully degrade when hardware/LLM backends are absent.
    """
    import os

    import app.main as _main
    from app.main import app

    old_env = os.environ.get("WS_AUTH_TOKEN")
    os.environ["WS_AUTH_TOKEN"] = "ws-test-token-12345"
    get_settings.cache_clear()

    _main.settings = get_settings()

    port = 19765
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    for _ in range(50):
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            break
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.1)
    else:
        pytest.fail("Server did not start within 5 s")

    yield f"ws://127.0.0.1:{port}"

    server.should_exit = True
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        if old_env is not None:
            os.environ["WS_AUTH_TOKEN"] = old_env
        else:
            os.environ.pop("WS_AUTH_TOKEN", None)
        get_settings.cache_clear()
        _main.settings = get_settings()


def _token():
    return get_settings().ws_auth_token


# ── 1. Metrics connection ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_metrics_connection(ws_server):
    """Connect to /ws/metrics, receive at least one metrics frame, disconnect."""
    async with websockets.connect(f"{ws_server}/ws/metrics?token={_token()}") as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
        data = json.loads(msg)
        assert "vram_used_mb" in data or "latency_ms" in data


# ── 2. Solve auth failure ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_solve_auth_failure(ws_server):
    """Connect to /api/v1/solve without a token — server must reject."""
    with pytest.raises(websockets.exceptions.InvalidStatus) as exc_info:
        async with websockets.connect(f"{ws_server}/api/v1/solve") as ws:
            pass
    assert exc_info.value.response.status_code == 403


# ── 3. Invalid JSON ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_solve_invalid_json(ws_server):
    """Send garbage bytes after connecting — expect an error frame."""
    async with websockets.connect(f"{ws_server}/api/v1/solve?token={_token()}") as ws:
        await ws.send("NOT_JSON{{{")
        msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
        data = json.loads(msg)
        assert data["type"] == "error"
        assert data["error"] == "pipeline_failure"


# ── 4. Missing action/query ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_solve_missing_action(ws_server):
    """Send valid JSON with no 'query' field — expect empty_query error."""
    async with websockets.connect(f"{ws_server}/api/v1/solve?token={_token()}") as ws:
        await ws.send(json.dumps({"action": "solve", "mode": "auto"}))
        msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
        data = json.loads(msg)
        assert data["type"] == "error"
        assert data["error"] == "empty_query"


# ── 5. Metrics broadcast to two clients ────────────────────────────────


@pytest.mark.asyncio
async def test_ws_metrics_broadcast(ws_server):
    """Two clients connected to /ws/metrics both receive the same broadcast."""
    url = f"{ws_server}/ws/metrics?token={_token()}"
    async with websockets.connect(url) as ws1, websockets.connect(url) as ws2:
        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=15.0))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=15.0))
        assert set(msg1.keys()) == set(msg2.keys())
