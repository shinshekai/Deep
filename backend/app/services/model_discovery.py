"""Model discovery across local runtimes and configured cloud providers."""

from __future__ import annotations

import os
import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from app.services.secrets import get_secret
from app.services.model_providers import BaseModelProvider, ProviderSpec

LOCAL_PROVIDERS: list[ProviderSpec] = []
CLOUD_PROVIDERS: list[ProviderSpec] = []

def _init_provider_lists():
    global LOCAL_PROVIDERS, CLOUD_PROVIDERS
    LOCAL_PROVIDERS = BaseModelProvider.get_local_specs()
    CLOUD_PROVIDERS = BaseModelProvider.get_cloud_specs()

_init_provider_lists()


def classify_model_capabilities(model_id: str) -> dict[str, Any]:
    """Tag models based on simple heuristics from their ID names."""
    mid = model_id.lower()
    capabilities = []

    # 1. Capability classification
    if any(x in mid for x in ["embed", "similarity", "bge", "nomic"]):
        capabilities.append("embedding")
    else:
        if any(x in mid for x in ["o1", "o3", "reasoning", "thought", "deepseek-r1", "preview"]):
            capabilities.append("reasoning")
        else:
            capabilities.append("chat")
            # If it's a known small model, it's also fast
            if any(x in mid for x in ["mini", "1.7b", "0.6b", "3b", "haiku", "flash", "small"]):
                capabilities.append("fast")

    # 2. Context Length Category
    context_length_cat = "unknown"
    if any(x in mid for x in ["32k", "32b-"]):
        context_length_cat = "medium"
    elif any(x in mid for x in ["128k", "1m", "flash", "gpt-4o", "claude-3", "o1", "o3"]):
        context_length_cat = "large"
    elif any(x in mid for x in ["8k", "4k", "2k", "0.6b", "1.7b"]):
        context_length_cat = "small"

    # 3. Parameter Size Category
    param_size_cat = "unknown"
    match = re.search(r"(\d+)b", mid)
    if match:
        size = int(match.group(1))
        if size < 7:
            param_size_cat = "small"
        elif size <= 32:
            param_size_cat = "medium"
        else:
            param_size_cat = "large"
    else:
        if "0.6b" in mid or "1.7b" in mid or "3b" in mid:
            param_size_cat = "small"
        elif (
            "8b" in mid or "14b" in mid or "32b" in mid or "qwen3-7b" in mid or "qwen3.6-7b" in mid
        ):
            param_size_cat = "medium"
        elif "70b" in mid or "35b" in mid or "moe" in mid or "30b" in mid:
            param_size_cat = "large"

    return {
        "capabilities": capabilities,
        "context_length_cat": context_length_cat,
        "parameter_size_cat": param_size_cat,
    }


class ModelDiscoveryService:
    """Discover available models without exposing provider secrets."""

    def __init__(self, lm_client=None, transport: httpx.AsyncBaseTransport | None = None):
        self.lm_client = lm_client
        self._transport = transport

    async def discover(
        self,
        active_selection: dict[str, Any] | None = None,
        active_selections: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "local": await self._discover_local(),
            "cloud": await self._discover_cloud(),
            "active_selection": active_selection,
            "active_selections": active_selections,
        }

    async def test_health(
        self,
        provider_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Perform an active, isolated health/latency check for a provider, with optional overrides."""
        spec = next((p for p in LOCAL_PROVIDERS + CLOUD_PROVIDERS if p.id == provider_id), None)
        if not spec:
            return {
                "status": "unavailable",
                "error": f"Unknown provider: {provider_id}",
                "latency_ms": 0.0,
                "model_count": 0,
            }

        resolved_key = api_key if api_key is not None else self._get_api_key(spec)
        resolved_base = base_url if base_url is not None else self._get_base_url(spec)

        if spec.source == "cloud" and not resolved_key:
            return {
                "status": "not_configured",
                "error": "API Key is required for cloud providers",
                "latency_ms": 0.0,
                "model_count": 0,
            }

        if not resolved_base:
            return {
                "status": "not_configured",
                "error": "Base URL is required",
                "latency_ms": 0.0,
                "model_count": 0,
            }

        if provider_id == "lm_studio":
            if not self.lm_client:
                return {
                    "status": "unavailable",
                    "error": "LM Studio client not configured in backend",
                    "latency_ms": 0.0,
                    "model_count": 0,
                }
            try:
                start_time = time.perf_counter()
                raw_models = await self.lm_client.list_models()
                latency = (time.perf_counter() - start_time) * 1000.0
                return {
                    "status": "available",
                    "latency_ms": round(latency, 2),
                    "model_count": len(raw_models),
                    "error": None,
                }
            except Exception as exc:
                return {
                    "status": "unavailable",
                    "error": str(exc),
                    "latency_ms": 0.0,
                    "model_count": 0,
                }

        try:
            url = self._models_url(spec, resolved_base, resolved_key)
            headers = self._headers(spec, resolved_key)

            start_time = time.perf_counter()
            async with httpx.AsyncClient(transport=self._transport, timeout=3.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
            latency = (time.perf_counter() - start_time) * 1000.0

            models = self._extract_models(spec, response.json())
            return {
                "status": "available",
                "latency_ms": round(latency, 2),
                "model_count": len(models),
                "error": None,
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "error": str(exc),
                "latency_ms": 0.0,
                "model_count": 0,
            }

    async def _discover_local(self) -> list[dict[str, Any]]:
        providers = []
        for spec in LOCAL_PROVIDERS:
            if spec.id == "lm_studio":
                providers.append(await self._discover_lm_studio(spec))
                continue
            providers.append(await self._discover_http_provider(spec))
        return providers

    async def _discover_cloud(self) -> list[dict[str, Any]]:
        providers = []
        for spec in CLOUD_PROVIDERS:
            providers.append(await self._discover_http_provider(spec))
        return providers

    async def _discover_lm_studio(self, spec: ProviderSpec) -> dict[str, Any]:
        if not self.lm_client:
            return self._provider_response(spec, "unavailable", [], configured=False)

        try:
            raw_models = await self.lm_client.list_models()
            models = [self._normalize_model(spec, model) for model in raw_models]
            return self._provider_response(spec, "available", models, configured=True)
        except Exception as exc:
            return self._provider_response(
                spec,
                "unavailable",
                [],
                configured=False,
                error=str(exc),
            )

    async def _discover_http_provider(self, spec: ProviderSpec) -> dict[str, Any]:
        api_key = self._get_api_key(spec)
        base_url = self._get_base_url(spec)

        configured = spec.enabled_without_config or bool(api_key or base_url)
        if spec.source == "cloud":
            configured = bool(api_key)
        if spec.base_url_env and not base_url and not spec.default_base_url:
            return self._provider_response(spec, "not_configured", [], configured=configured)
        if spec.api_key_env and not api_key:
            return self._provider_response(spec, "not_configured", [], configured=False)
        if not base_url:
            return self._provider_response(spec, "not_configured", [], configured=configured)

        try:
            url = self._models_url(spec, base_url, api_key)
            headers = self._headers(spec, api_key)
            async with httpx.AsyncClient(transport=self._transport, timeout=3.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
            models = [
                self._normalize_model(spec, model)
                for model in self._extract_models(spec, response.json())
            ]
            return self._provider_response(
                spec, "available", models, configured=configured, base_url=base_url
            )
        except Exception as exc:
            return self._provider_response(
                spec,
                "unavailable",
                [],
                configured=configured,
                base_url=base_url,
                error=str(exc),
            )

    def _provider_response(
        self,
        spec: ProviderSpec,
        status: str,
        models: list[dict[str, Any]],
        configured: bool,
        base_url: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "id": spec.id,
            "name": spec.name,
            "source": spec.source,
            "status": status,
            "configured": configured,
            "openai_compatible": spec.openai_compatible,
            "models": models,
            "cost_hint": spec.cost_hint,
            "latency_hint": spec.latency_hint,
            "description": spec.description,
            "setup_docs_url": spec.setup_docs_url,
        }
        if base_url:
            data["base_url"] = base_url
        if error:
            data["error"] = error
        return data

    def _normalize_model(self, spec: ProviderSpec, model: dict[str, Any]) -> dict[str, Any]:
        model_id = model.get("id") or model.get("model") or model.get("name") or ""
        display_name = (
            model.get("name") or model.get("display_name") or model.get("displayName") or model_id
        )
        details = model.get("details") or {}
        capabilities_info = classify_model_capabilities(model_id)
        return {
            "id": model_id,
            "name": display_name,
            "provider_id": spec.id,
            "source": spec.source,
            "openai_compatible": spec.openai_compatible,
            "metadata": {
                "object": model.get("object"),
                "family": details.get("family"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
                "context_length": model.get("context_length")
                or capabilities_info.get("context_length_cat"),
                "capabilities": capabilities_info["capabilities"],
                "context_length_cat": capabilities_info["context_length_cat"],
                "parameter_size_cat": capabilities_info["parameter_size_cat"],
            },
        }

    def _extract_models(self, spec: ProviderSpec, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if spec.id == "ollama":
            return payload.get("models", [])
        if spec.id == "gemini":
            return payload.get("models", [])
        if spec.id == "vertex":
            return (
                payload.get("publisherModels") or payload.get("models") or payload.get("data", [])
            )
        return payload.get("data", [])

    def _get_api_key(self, spec: ProviderSpec) -> str:
        if not spec.api_key_env:
            return ""
        keys = spec.api_key_env if isinstance(spec.api_key_env, tuple) else (spec.api_key_env,)
        for key in keys:
            value = get_secret(key)
            if value:
                return value
        return ""

    def _get_base_url(self, spec: ProviderSpec) -> str:
        if spec.base_url_env:
            value = os.environ.get(spec.base_url_env, "")
            if value:
                return value.rstrip("/")
        return (spec.default_base_url or "").rstrip("/")

    def _models_url(self, spec: ProviderSpec, base_url: str, api_key: str) -> str:
        if spec.id == "vertex" and spec.base_url_env and os.environ.get(spec.base_url_env):
            return base_url
        url = urljoin(f"{base_url}/", spec.models_path.lstrip("/"))
        if spec.auth_style == "query_key":
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}key={api_key}"
        return url

    def _headers(self, spec: ProviderSpec, api_key: str) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if not api_key:
            return headers
        if spec.auth_style == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        elif spec.auth_style == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        return headers
