"""Model discovery tests."""

import httpx
import pytest

from app.services.model_discovery import ModelDiscoveryService


class StubLMClient:
    async def list_models(self):
        return [
            {"id": "qwen/qwen3.6-35b-a3b", "object": "model"},
            {"id": "text-embedding-qwen3-embedding-8b", "object": "model"},
        ]


@pytest.mark.asyncio
async def test_discover_lm_studio_models():
    service = ModelDiscoveryService(lm_client=StubLMClient())

    result = await service.discover()

    lm_studio = next(p for p in result["local"] if p["id"] == "lm_studio")
    assert lm_studio["status"] == "available"
    assert [m["id"] for m in lm_studio["models"]] == [
        "qwen/qwen3.6-35b-a3b",
        "text-embedding-qwen3-embedding-8b",
    ]
    assert all(m["source"] == "local" for m in lm_studio["models"])


@pytest.mark.asyncio
async def test_cloud_provider_key_status_does_not_expose_secret(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-test-secret"
        return httpx.Response(
            200,
            json={"data": [{"id": "gpt-test", "object": "model"}]},
        )

    transport = httpx.MockTransport(handler)
    service = ModelDiscoveryService(lm_client=StubLMClient(), transport=transport)

    result = await service.discover()

    openai = next(p for p in result["cloud"] if p["id"] == "openai")
    assert openai["configured"] is True
    assert "sk-test-secret" not in str(openai)
    assert openai["models"][0]["id"] == "gpt-test"
    assert openai["models"][0]["source"] == "cloud"


@pytest.mark.asyncio
async def test_unconfigured_cloud_provider_is_not_called(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    called_openai = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called_openai
        if request.url.host == "api.openai.com":
            called_openai = True
        return httpx.Response(500)

    service = ModelDiscoveryService(
        lm_client=StubLMClient(),
        transport=httpx.MockTransport(handler),
    )

    result = await service.discover()

    openai = next(p for p in result["cloud"] if p["id"] == "openai")
    assert openai["configured"] is False
    assert openai["models"] == []
    assert called_openai is False


@pytest.mark.asyncio
async def test_classify_model_capabilities():
    from app.services.model_discovery import classify_model_capabilities

    res1 = classify_model_capabilities("deepseek-r1-distill-qwen-8b")
    assert "reasoning" in res1["capabilities"]
    assert res1["parameter_size_cat"] == "medium"

    res2 = classify_model_capabilities("qwen3-0.6b-chat")
    assert "chat" in res2["capabilities"]
    assert "fast" in res2["capabilities"]
    assert res2["parameter_size_cat"] == "small"

    res3 = classify_model_capabilities("nomic-embed-text-v1.5")
    assert "embedding" in res3["capabilities"]


@pytest.mark.asyncio
async def test_health_check_available():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "gpt-test", "object": "model"}]},
        )

    transport = httpx.MockTransport(handler)
    service = ModelDiscoveryService(lm_client=StubLMClient(), transport=transport)

    health = await service.test_health(
        "openai", api_key="test-key", base_url="https://api.openai.com"
    )
    assert health["status"] == "available"
    assert health["latency_ms"] >= 0.0
    assert health["model_count"] == 1
    assert health["error"] is None
