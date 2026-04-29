"""LM Studio client — model mgmt, health, streaming chat completion."""

import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LMStudioClient:
    """HTTP client for LM Studio's OpenAI-compatible API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 metrics_callback=None):
        settings = get_settings()
        self.base_url = (base_url or settings.llm_host
                         or f"http://localhost:{settings.llm_port}")
        self.api_key = api_key or settings.llm_api_key or "lm-studio"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._metrics_callback = metrics_callback

        # Priority Queue + Semaphores (Phase 2)
        self._queue = asyncio.PriorityQueue()
        self._semaphores = {
            1: asyncio.Semaphore(4), # Tier 1 (Retrieval)
            2: asyncio.Semaphore(2), # Tier 2 (Reasoning)
            3: asyncio.Semaphore(1), # Tier 3 (Generation)
        }
        self.queue_depths = {1: 0, 2: 0, 3: 0}

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
        """Load a model into LM Studio via REST API or CLI fallback."""
        logger.info(f"Loading model: {model_id}")
        # Try REST API first
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v0/models/load",
                    json={"model": model_id},
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    logger.info(f"Model {model_id} loaded via REST API")
                    return True
                else:
                    logger.warning(
                        f"REST API load failed with status {resp.status_code}: {resp.text[:200]}"
                    )
        except Exception as e:
            logger.warning(f"REST API load failed: {e}")

        # Fallback to lms CLI
        logger.info(f"Falling back to CLI for loading {model_id}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "lms", "load", model_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(f"Model {model_id} loaded via CLI")
                return True
            else:
                err_msg = stderr.decode().strip() if stderr else "No error output"
                logger.error(
                    f"CLI load failed (exit code {proc.returncode}): {err_msg}"
                )
                return False
        except Exception as e:
            logger.error(f"CLI load failed: {e}")
            return False

    async def unload_model(self, model_id: str) -> bool:
        """Unload a model from LM Studio via REST API or CLI fallback."""
        logger.info(f"Unloading model: {model_id}")
        # Try REST API first
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v0/models/unload",
                    json={"model": model_id},
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    logger.info(f"Model {model_id} unloaded via REST API")
                    return True
                else:
                    logger.warning(
                        f"REST API unload failed with status {resp.status_code}: {resp.text[:200]}"
                    )
        except Exception as e:
            logger.warning(f"REST API unload failed: {e}")

        # Fallback to lms CLI
        logger.info(f"Falling back to CLI for unloading {model_id}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "lms", "unload", model_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(f"Model {model_id} unloaded via CLI")
                return True
            else:
                err_msg = stderr.decode().strip() if stderr else "No error output"
                logger.error(
                    f"CLI unload failed (exit code {proc.returncode}): {err_msg}"
                )
                return False
        except Exception as e:
            logger.error(f"CLI unload failed: {e}")
            return False

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Call LM Studio /v1/embeddings endpoint.

        Returns list of embedding vectors in input order.
        Uses embedding_host / embedding_model / embedding_api_key from settings
        when configured; falls back to primary LLM host otherwise.
        Returns [] on any error so callers can degrade gracefully.
        """
        settings = get_settings()
        base = settings.embedding_host or self.base_url
        api_key = settings.embedding_api_key or self.api_key
        embed_model = model or settings.embedding_model or ""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {"input": texts}
        if embed_model:
            body["model"] = embed_model

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{base}/v1/embeddings",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                # Sort by index to preserve input order
                data_sorted = sorted(data, key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in data_sorted]
        except Exception as e:
            logger.error(f"embed() failed: {e}")
            return []

    async def stream_chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        chunk_callback=None,
    ) -> dict:
        """Stream chat completion and return dict with 'content' key.

        Returns {"content": str} on success or {"error": str(e)} on failure.
        Delegates to `stream_chat` to avoid duplicated streaming logic.
        """
        try:
            content = await self.stream_chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=0.7,
                chunk_callback=chunk_callback,
            )
            return {"content": content if content else ""}
        except Exception as e:
            logger.error(f"stream_chat_completion failed: {e}")
            return {"error": str(e)}

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        priority: int = 2,
        chunk_callback=None,
    ) -> str | None:
        """Stream chat completion and return full content string.
        Uses Priority Queue and Semaphores to govern concurrent execution.
        priority: 1 (Retrieval), 2 (Reasoning), 3 (Generation)
        """
        self.queue_depths[priority] += 1
        # Update metrics via callback (avoid circular import)
        if self._metrics_callback:
            self._metrics_callback({
                "queue_depths": {
                    "retrieval": self.queue_depths.get(1, 0),
                    "reasoning": self.queue_depths.get(2, 0),
                    "generation": self.queue_depths.get(3, 0),
                }
            })
            
        future = asyncio.get_running_loop().create_future()
        
        async def _execute():
            try:
                # Use semaphore for concurrency limits
                sem = self._semaphores.get(priority, self._semaphores[3])
                async with sem:
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
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        tok = delta.get("content", "")
                                        if tok:
                                            content.append(tok)
                                            if chunk_callback:
                                                if asyncio.iscoroutinefunction(chunk_callback):
                                                    await chunk_callback(tok)
                                                else:
                                                    chunk_callback(tok)
                                    except json.JSONDecodeError:
                                        pass
                    future.set_result("".join(content) if content else None)
            except Exception as e:
                logger.error(f"stream_chat failed: {e}")
                future.set_exception(e)
            finally:
                self.queue_depths[priority] -= 1
                if self._metrics_callback:
                    self._metrics_callback({
                        "queue_depths": {
                            "retrieval": self.queue_depths.get(1, 0),
                            "reasoning": self.queue_depths.get(2, 0),
                            "generation": self.queue_depths.get(3, 0)
                        }
                    })

        # Put task in priority queue
        await self._queue.put((priority, time.time(), _execute))
        
        # We need a worker to process the queue if it's not already running.
        # But instead of a background worker, let's just create a task to process it
        # immediately so it executes according to priority.
        _ = asyncio.create_task(self._process_next())
        
        try:
            return await future
        except Exception:
            return None

    async def _process_next(self):
        """Worker to process the next item in the priority queue."""
        if not self._queue.empty():
            _, _, func = await self._queue.get()
            await func()
            self._queue.task_done()


