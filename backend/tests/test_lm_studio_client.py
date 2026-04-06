"""Tests for LM Studio client stream_chat_completion."""

import pytest


@pytest.mark.asyncio
async def test_stream_chat_completion_exists():
    from app.services.lm_studio_client import LMStudioClient
    client = LMStudioClient()
    assert callable(getattr(client, "stream_chat_completion", None))


@pytest.mark.asyncio
async def test_stream_chat_completion_returns_dict():
    """stream_chat_completion should return a dict with 'content' key on success."""
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import AsyncMock, patch, MagicMock
    import json

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    # Build a mock streaming response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        chunks = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            'data: [DONE]',
        ]
        for chunk in chunks:
            yield chunk

    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_client):
        result = await client.stream_chat_completion(
            model="Qwen3-4B-Q4_K_M",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
        )

    assert isinstance(result, dict)
    assert "content" in result
    assert result["content"] == "Hello world"
    assert "error" not in result


@pytest.mark.asyncio
async def test_stream_chat_completion_returns_error_on_failure():
    """stream_chat_completion should return a dict with 'error' key on failure."""
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock
    import httpx

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.side_effect = httpx.ConnectError("Connection refused")
        result = await client.stream_chat_completion(
            model="Qwen3-4B-Q4_K_M",
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert isinstance(result, dict)
    assert "error" in result
