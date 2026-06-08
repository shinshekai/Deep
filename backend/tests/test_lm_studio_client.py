"""Tests for LM Studio client stream_chat_completion."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_stream_chat_completion_returns_dict():
    """stream_chat_completion should return a dict with 'content' key on success."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

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
            "data: [DONE]",
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
    """stream_chat_completion should return an error dict when LLM is not reachable.

    The previous behaviour returned ``{"content": ""}`` which was
    indistinguishable from a successful empty response. Day 12b raised
    the error in ``stream_chat``; this wrapper translates the raised
    exception into ``{"error": "..."}`` so clients can detect the
    failure without crashing on a missing ``content`` key.
    """
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.side_effect = httpx.ConnectError("Connection refused")
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            result = await client.stream_chat_completion(
                model="Qwen3-4B-Q4_K_M",
                messages=[{"role": "user", "content": "Hi"}],
            )

    assert isinstance(result, dict)
    assert "error" in result
    assert "Connection refused" in result["error"]
    # "content" key is absent on error (was the buggy old behavior)
    assert "content" not in result


@pytest.mark.asyncio
async def test_check_health_success():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

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
    from unittest.mock import patch

    import httpx

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    with patch("app.services.lm_studio_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.side_effect = httpx.ConnectError(
            "Connection refused"
        )
        assert await client.check_health() is False


@pytest.mark.asyncio
async def test_list_models():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"id": "model_1"}]}
    mock_resp.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        models = await client.list_models()
        assert len(models) == 1
        assert models[0]["id"] == "model_1"


@pytest.mark.asyncio
async def test_load_model_success():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.list_models = AsyncMock(return_value=[{"id": "test_model"}])

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        with patch("asyncio.sleep", AsyncMock()):
            assert await client.load_model("test_model") is True


@pytest.mark.asyncio
async def test_unload_model_success():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    # `unload_model` has a post-unload verification loop that calls
    # ``list_models`` 5 times; provide a response for both verbs.
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": []}  # empty → "unloaded"

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp
    mock_client_instance.get.return_value = mock_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        with patch("asyncio.sleep", AsyncMock()):
            assert await client.unload_model("test_model") is True


@pytest.mark.asyncio
async def test_embed_success():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        embeddings = await client.embed(["text1", "text2"])
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_load_model_cli_fallback():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 500  # REST fail

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            client.list_models = AsyncMock(return_value=[{"id": "test_model"}])
            with patch("asyncio.sleep", AsyncMock()):
                assert await client.load_model("test_model") is True


@pytest.mark.asyncio
async def test_unload_model_cli_fallback():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()

    # REST returns 500 → falls back to CLI. The 5-iteration verification
    # loop then calls list_models (GET) and expects the model is gone.
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.json.return_value = {"data": []}

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_resp_500
    mock_client_instance.get.return_value = mock_resp_500

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with patch("asyncio.sleep", AsyncMock()):
                import sys

                class FakePynvml:
                    def nvmlInit(self):
                        pass

                    def nvmlDeviceGetCount(self):
                        return 1

                    def nvmlDeviceGetHandleByIndex(self, i):
                        return "handle"

                    def nvmlDeviceGetMemoryInfo(self, h):
                        class Info:
                            used = 1000

                        return Info()

                sys.modules["pynvml"] = FakePynvml()
                try:
                    assert await client.unload_model("test_model") is True
                finally:
                    del sys.modules["pynvml"]


# ---------------------------------------------------------------------------
# Day 8a: retry-with-backoff coverage for load_model, unload_model, stream_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_model_retries_on_500_then_succeeds(monkeypatch):
    """load_model: two 500s then a 200 — _with_retry should recover on the third try."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}
    client.list_models = AsyncMock(return_value=[{"id": "test_model"}])

    # Build 3 sequential responses: 500, 500, 200
    responses = []
    for status in (500, 500, 200):
        r = MagicMock()
        r.status_code = status
        # raise_for_status on 500 raises HTTPStatusError so _with_retry sees it
        if status >= 400:
            r.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    f"Server Error {status}",
                    request=MagicMock(),
                    response=MagicMock(status_code=status),
                )
            )
        else:
            r.raise_for_status = MagicMock()
        responses.append(r)

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(side_effect=responses)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            assert await client.load_model("test_model") is True

    # 3 attempts means 3 client creations → 3 enter calls
    assert mock_ctx.__aenter__.await_count == 3


@pytest.mark.asyncio
async def test_load_model_falls_back_to_cli_after_all_retries_fail(monkeypatch):
    """load_model: 3 × 500 → falls back to CLI on final failure."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}
    client.list_models = AsyncMock(return_value=[{"id": "test_model"}])

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Server Error 500",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
    )
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_resp)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
    mock_proc.returncode = 0

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
                assert await client.load_model("test_model") is True

    # 3 REST attempts before giving up
    assert mock_client_instance.post.await_count == 3


@pytest.mark.asyncio
async def test_unload_model_retries_on_network_error_then_succeeds():
    """unload_model: two ConnectErrors then a 200 — _with_retry should recover."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    ok_resp = MagicMock()
    ok_resp.status_code = 200

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = {"data": []}

    # post fails twice with ConnectError, then succeeds with 200
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(
        side_effect=[
            httpx.ConnectError("Connection refused"),
            httpx.ConnectError("Connection refused"),
            ok_resp,
        ]
    )
    mock_client_instance.get = AsyncMock(return_value=list_resp)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client_instance
    mock_ctx.__aexit__.return_value = None

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_ctx):
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            assert await client.unload_model("test_model") is True

    # 3 attempts on the REST unload (2 fail + 1 succeed) and 1 for the
    # list_models() verification loop → 4 total httpx client opens.
    assert mock_client_instance.post.await_count == 3
    assert mock_ctx.__aenter__.await_count == 4


@pytest.mark.asyncio
async def test_stream_chat_open_retries_on_connect_error():
    """stream_chat's initial handshake retries on ConnectError before giving up."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    # Two ConnectErrors on open_stream, then a clean response on attempt 3
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.raise_for_status = MagicMock()

    async def ok_aiter_lines():
        for line in ['data: {"choices": [{"delta": {"content": "hi"}}]}', "data: [DONE]"]:
            yield line

    ok_response.aiter_lines = ok_aiter_lines
    ok_response.__aenter__ = AsyncMock(return_value=ok_response)
    ok_response.__aexit__ = AsyncMock(return_value=None)

    ok_client = AsyncMock()
    ok_client.stream = MagicMock(return_value=ok_response)
    ok_client.aclose = AsyncMock()

    call_count = {"n": 0}

    def factory_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise httpx.ConnectError("Connection refused")
        return ok_client

    with patch("app.services.lm_studio_client.httpx.AsyncClient", side_effect=factory_side_effect):
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            result = await client.stream_chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="Qwen3-4B-Q4_K_M",
                max_tokens=64,
            )

    assert result == "hi"
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_with_retry_unit():
    """Direct unit test of _with_retry: count attempts and verify last-exc raise."""
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.services.lm_studio_client import _with_retry

    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        raise httpx.ConnectError(f"fail {calls['n']}")

    with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
        with pytest.raises(httpx.ConnectError):
            await _with_retry(factory, attempts=3, backoff=0.01, label="unit")

    assert calls["n"] == 3


# ---------------------------------------------------------------------------
# Day 12b: stream_chat() surfaces error context (raises) instead of None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_chat_propagates_exception_instead_of_returning_none():
    """stream_chat() must raise on transport failure — callers (and
    stream_chat_completion) can then distinguish 'no tokens yet' (empty
    string) from 'request failed' (raised exception). The old behaviour
    returned None for both, masking transient errors as silent empty
    responses."""
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    with patch(
        "app.services.lm_studio_client.httpx.AsyncClient", side_effect=httpx.ConnectError("boom")
    ):
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            with pytest.raises(httpx.ConnectError):
                await client.stream_chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="Qwen3-4B-Q4_K_M",
                    max_tokens=64,
                )


@pytest.mark.asyncio
async def test_stream_chat_returns_empty_string_for_zero_tokens():
    """When the model returns zero content tokens, stream_chat should
    return '' — not None. Empty string is the canonical 'no answer'
    value; None was ambiguous with 'error'."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def empty_aiter():
        # Server sends [DONE] immediately, no content deltas
        yield "data: [DONE]"

    mock_response.aiter_lines = empty_aiter
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()

    with patch("app.services.lm_studio_client.httpx.AsyncClient", return_value=mock_client):
        result = await client.stream_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="Qwen3-4B-Q4_K_M",
            max_tokens=64,
        )
    assert result == ""
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_stream_chat_completion_wraps_error_in_dict():
    """The convenience wrapper stream_chat_completion() must still
    translate the now-raised exception into a dict with 'error' key,
    so callers that depend on the dict-shaped response don't break."""
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.services.lm_studio_client import LMStudioClient

    client = LMStudioClient()
    client.base_url = "http://localhost:1234"
    client._headers = {"Authorization": "Bearer lm-studio", "Content-Type": "application/json"}

    with patch(
        "app.services.lm_studio_client.httpx.AsyncClient",
        side_effect=httpx.ConnectError("server gone"),
    ):
        with patch("app.services.lm_studio_client.asyncio.sleep", AsyncMock()):
            result = await client.stream_chat_completion(
                model="Qwen3-4B-Q4_K_M",
                messages=[{"role": "user", "content": "hi"}],
            )
    assert isinstance(result, dict)
    assert "error" in result
    assert "server gone" in result["error"]
    assert "content" not in result
