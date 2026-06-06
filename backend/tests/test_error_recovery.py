"""Error recovery path tests.

Verifies the API gracefully handles internal failures (LLM timeouts,
connection errors, disk-full, etc.) without returning raw 500s.
"""

import asyncio
import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from httpx import ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_lm_client_timeout():
    """TimeoutError from lm_client.stream_chat is caught; response is not 500."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.lm_client") as mock_lm:
            mock_lm.check_health = AsyncMock(return_value=True)
            mock_lm.stream_chat = AsyncMock(side_effect=TimeoutError("LLM timed out"))
            with patch("app.state.vram_monitor") as mock_vm:
                mock_vm.poll_once = AsyncMock(return_value={
                    "vram_total_mb": 16000, "vram_used_mb": 8000,
                    "vram_used_pct": 50.0, "gpu_available": True,
                })
                resp = await client.post("/api/v1/query", json={
                    "query": "What is deep learning?",
                    "kb_name": "default",
                    "device_id": "test-device",
                })

        assert resp.status_code < 500
        data = resp.json()
        assert "answer" in data
        assert "error" in data["answer"].lower() or "timeout" in data["answer"].lower()


@pytest.mark.asyncio
async def test_lm_client_connection_error():
    """ConnectionError from lm_client is caught; response is not 500."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.lm_client") as mock_lm:
            mock_lm.check_health = AsyncMock(return_value=True)
            mock_lm.stream_chat = AsyncMock(side_effect=ConnectionError("LM Studio unreachable"))
            with patch("app.state.vram_monitor") as mock_vm:
                mock_vm.poll_once = AsyncMock(return_value={
                    "vram_total_mb": 16000, "vram_used_mb": 8000,
                    "vram_used_pct": 50.0, "gpu_available": True,
                })
                resp = await client.post("/api/v1/query", json={
                    "query": "Summarize this document",
                    "kb_name": "default",
                    "device_id": "test-device",
                })

        assert resp.status_code < 500
        data = resp.json()
        assert "answer" in data


@pytest.mark.asyncio
async def test_vram_monitor_unavailable():
    """Health endpoint still responds when vram_monitor returns zeros."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={
                "vram_total_mb": 0,
                "vram_used_mb": 0,
                "vram_used_pct": 0,
                "gpu_available": False,
            })
            with patch("app.state.lm_client") as mock_lm:
                mock_lm.check_health = AsyncMock(return_value=True)
                resp = await client.get("/api/v1/health")

        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert data["gpu"] is False


@pytest.mark.asyncio
async def test_model_load_failure():
    """Exception from model_manager.load_model is caught; response is not 500."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.model_manager") as mock_mm:
            mock_mm.load_model = AsyncMock(side_effect=Exception("CUDA OOM"))
            with patch("app.state.lm_client") as mock_lm:
                mock_lm.load_model = AsyncMock(side_effect=Exception("CUDA OOM"))
                resp = await client.post("/api/v1/models/bad-model/load")

        assert resp.status_code != 500
        data = resp.json()
        assert "model_id" in data
        assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_disk_full_on_upload():
    """OSError during file write is caught; upload task status is 'failed'."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.lm_client") as mock_lm:
            mock_lm.check_health = AsyncMock(return_value=True)
            with patch("pathlib.Path.write_bytes", side_effect=OSError("No space left on device")):
                resp = await client.post(
                    "/api/v1/knowledge/upload",
                    files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
                    data={"kb_name": "default"},
                )

        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        # Let the background task run and fail
        await asyncio.sleep(0.3)

        task_resp = await client.get(f"/api/v1/knowledge/tasks/{task_id}")
        assert task_resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_concurrent_request_handling():
    """5 rapid concurrent requests all complete without crashing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.state.lm_client") as mock_lm:
            mock_lm.check_health = AsyncMock(return_value=True)
            mock_lm.stream_chat = AsyncMock(return_value="Concurrent answer")
            with patch("app.state.vram_monitor") as mock_vm:
                mock_vm.poll_once = AsyncMock(return_value={
                    "vram_total_mb": 16000, "vram_used_mb": 8000,
                    "vram_used_pct": 50.0, "gpu_available": True,
                })

                tasks = [
                    client.post("/api/v1/query", json={
                        "query": f"Concurrent query {i}",
                        "kb_name": "default",
                        "device_id": "test-device",
                    })
                    for i in range(5)
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            assert isinstance(resp, httpx.Response), f"Request raised: {resp}"
            assert resp.status_code < 500, f"Request returned {resp.status_code}"
