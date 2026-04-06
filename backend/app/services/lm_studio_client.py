"""LM Studio client — model mgmt, health, streaming chat completion."""

import asyncio
import json
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LMStudioClient:
    """HTTP client for LM Studio's OpenAI-compatible API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.llm_host
                         or f"http://localhost:{settings.llm_port}")
        self.api_key = api_key or settings.llm_api_key or "lm-studio"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models",
                                        headers=self._headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models",
                                        headers=self._headers)
                resp.raise_for_status()
                return resp.json().get("data", [])
        except Exception as e:
            logger.error(f"list_models failed: {e}")
            return []

    async def load_model(self, model_id: str) -> bool:
        logger.info(f"Model load requested: {model_id}")
        return True

    async def unload_model(self, model_id: str) -> bool:
        logger.info(f"Model unload requested: {model_id}")
        return True

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str | None:
        """Stream chat completion and return full content string."""
        try:
            body: dict = {
                "messages": messages,
                "stream": True,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if model:
                body["model"] = model

            content = []
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=body,
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get(
                                    "delta", {})
                                tok = delta.get("content", "")
                                if tok:
                                    content.append(tok)
                            except json.JSONDecodeError:
                                pass

            return "".join(content) if content else None
        except Exception as e:
            logger.error(f"stream_chat failed: {e}")
            return None
