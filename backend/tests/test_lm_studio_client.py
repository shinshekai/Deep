"""Tests for LM Studio client stream_chat_completion."""

import pytest


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
async def test_stream_chat_completion_handles_llm_unavailable():
    """stream_chat_completion should return empty content when LLM is not reachable."""
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

    # Delegates to stream_chat which catches exceptions and returns None,
    # so stream_chat_completion wraps that as empty content
    assert isinstance(result, dict)
    assert "content" in result
    assert result["content"] == ""

@pytest.mark.asyncio
async def test_check_health_success():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        assert await client.check_health() is True

@pytest.mark.asyncio
async def test_check_health_failure():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock
    import httpx
    client = LMStudioClient()
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.side_effect = httpx.ConnectError("Connection refused")
        assert await client.check_health() is False

@pytest.mark.asyncio
async def test_list_models():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"id": "model_1"}]}
    mock_resp.raise_for_status = MagicMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        models = await client.list_models()
        assert len(models) == 1
        assert models[0]["id"] == "model_1"

@pytest.mark.asyncio
async def test_load_model_success():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    client.list_models = AsyncMock(return_value=[{"id": "test_model"}])
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        with patch("asyncio.sleep", AsyncMock()):
            assert await client.load_model("test_model") is True

@pytest.mark.asyncio
async def test_unload_model_success():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        with patch("asyncio.sleep", AsyncMock()):
            assert await client.unload_model("test_model") is True

@pytest.mark.asyncio
async def test_embed_success():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]}
    mock_resp.raise_for_status = MagicMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        embeddings = await client.embed(["text1", "text2"])
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]

@pytest.mark.asyncio
async def test_load_model_cli_fallback():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 500  # REST fail
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            client.list_models = AsyncMock(return_value=[{"id": "test_model"}])
            with patch("asyncio.sleep", AsyncMock()):
                assert await client.load_model("test_model") is True

@pytest.mark.asyncio
async def test_unload_model_cli_fallback():
    from app.services.lm_studio_client import LMStudioClient
    from unittest.mock import patch, AsyncMock, MagicMock
    client = LMStudioClient()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 500  # REST fail
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    
    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client_instance
        
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with patch("asyncio.sleep", AsyncMock()):
                import sys
                class FakePynvml:
                    def nvmlInit(self): pass
                    def nvmlDeviceGetCount(self): return 1
                    def nvmlDeviceGetHandleByIndex(self, i): return "handle"
                    def nvmlDeviceGetMemoryInfo(self, h):
                        class Info: used = 1000
                        return Info()
                sys.modules['pynvml'] = FakePynvml()
                try:
                    assert await client.unload_model("test_model") is True
                finally:
                    del sys.modules['pynvml']
