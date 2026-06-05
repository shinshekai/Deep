"""LM Studio client — model mgmt, health, streaming chat completion."""

import asyncio
import json
import logging
import random
import re
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Whitelist pattern for model ids. ``lms load`` / ``lms unload`` are
# invoked via ``create_subprocess_exec`` which already prevents shell
# injection, but we still constrain the charset so that a user-supplied
# value cannot be interpreted as a flag or path by the ``lms`` CLI.
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._:/\-]{1,128}$")


def _validate_model_id(model_id: str) -> str:
    """Reject model ids outside the safe character set before CLI use."""
    if not isinstance(model_id, str) or not _MODEL_ID_RE.match(model_id):
        raise ValueError(
            f"Refusing to pass model_id to lms CLI: {model_id!r} "
            "does not match [A-Za-z0-9._:/-] or is too long."
        )
    return model_id


# Default retry configuration for transient HTTP failures.
# Conservative counts — single transient blip should not double latency.
_DEFAULT_RETRY_ATTEMPTS = 3
_DEFAULT_RETRY_BACKOFF = 0.5  # seconds
_RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


async def _with_retry(
    coro_factory,
    *,
    attempts: int = _DEFAULT_RETRY_ATTEMPTS,
    backoff: float = _DEFAULT_RETRY_BACKOFF,
    label: str = "request",
):
    """Run ``coro_factory()`` with exponential backoff on transient errors.

    The factory is called fresh for each attempt because httpx clients and
    response objects are single-use. Returns the coroutine result on success
    or raises the last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_factory()
        except httpx.HTTPStatusError as e:
            last_exc = e
            status = e.response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == attempts:
                raise
            delay = backoff * (2 ** (attempt - 1))
            delay += random.uniform(0, backoff)  # jitter
            logger.warning(
                "%s retry %d/%d after %.2fs (status=%d)",
                label, attempt, attempts, delay, status,
            )
            await asyncio.sleep(delay)
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            if attempt == attempts:
                raise
            delay = backoff * (2 ** (attempt - 1))
            delay += random.uniform(0, backoff)
            logger.warning(
                "%s retry %d/%d after %.2fs (%s: %s)",
                label, attempt, attempts, delay, type(e).__name__, e,
            )
            await asyncio.sleep(delay)
    # Unreachable — the loop either returns or raises — but keep mypy happy
    raise last_exc  # type: ignore[misc]


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

    def configure_endpoint(self, base_url: str, api_key: str | None = None):
        """Point the OpenAI-compatible client at the selected provider.

        Rejects base URLs that point at internal networks, link-local
        addresses, or cloud metadata endpoints. Loopback / private ranges
        require the ``UDIP_ALLOW_LOCAL_LLM`` env flag to be set first.
        """
        from app.services.security import is_safe_base_url  # avoid circular import

        if not is_safe_base_url(base_url):
            raise ValueError(
                f"Refusing to configure LLM endpoint at {base_url!r} — "
                "SSRF protection. Set UDIP_ALLOW_LOCAL_LLM=1 for local "
                "LM Studio / Ollama, or use a publicly reachable host."
            )
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3]
        self.base_url = normalized
        if api_key:
            self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def check_health(self) -> bool:
        async def _do_request():
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/models", headers=self._headers
                )
                return resp.status_code == 200
        try:
            return await _with_retry(_do_request, label="check_health")
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        async def _do_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/models", headers=self._headers
                )
                resp.raise_for_status()
                return resp.json().get("data", [])
        try:
            return await _with_retry(_do_request, label="list_models")
        except Exception as e:
            logger.error(f"list_models failed: {e}")
            return []

    async def load_model(self, model_id: str, cache_type_k: str | None = None, cache_type_v: str | None = None) -> bool:
        """Load a model into LM Studio via REST API or CLI fallback.

        ``model_id`` is whitelist-validated before being passed to the
        ``lms`` CLI subprocess. The REST call is retried with exponential
        backoff (3 attempts, 0.5s/1s/2s) on transient errors before
        falling back to the CLI.
        """
        try:
            model_id = _validate_model_id(model_id)
        except ValueError as e:
            logger.error(f"load_model rejected: {e}")
            return False
        logger.info(f"Loading model: {model_id}")

        payload = {"model": model_id}
        if cache_type_k:
            payload["cache_type_k"] = cache_type_k
        if cache_type_v:
            payload["cache_type_v"] = cache_type_v

        load_success = False
        # Try REST API first (with retry)
        async def _do_load_request():
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v0/models/load",
                    json=payload,
                    headers=self._headers,
                )
                resp.raise_for_status()  # surface 5xx so _with_retry can retry
                return resp

        try:
            resp = await _with_retry(_do_load_request, label="load_model")
            if resp.status_code == 200:
                logger.info(f"Model {model_id} load requested via REST API")
                load_success = True
            else:
                logger.warning(f"REST API load failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"REST API load failed after retries: {e}")

        # Fallback to CLI
        if not load_success:
            logger.info(f"Falling back to CLI for loading {model_id}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "lms", "load", model_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    logger.info(f"Model {model_id} load requested via CLI")
                    load_success = True
                else:
                    logger.error(f"CLI load failed: {stderr.decode().strip() if stderr else ''}")
            except Exception as e:
                logger.error(f"CLI load failed: {e}")
                
        if not load_success:
            return False
            
        # Verify load via /v1/models poll
        for _ in range(5):
            await asyncio.sleep(2.0)
            models = await self.list_models()
            if any(m.get("id") == model_id for m in models):
                logger.info(f"Verified model {model_id} is loaded and ready.")
                return True
        logger.error(f"Failed to verify load of {model_id}")
        return False

    async def unload_model(self, model_id: str) -> bool:
        """Unload a model from LM Studio via REST API or CLI fallback.

        ``model_id`` is whitelist-validated before being passed to the
        ``lms`` CLI subprocess. The REST call is retried with exponential
        backoff (3 attempts, 0.5s/1s/2s) on transient errors before
        falling back to the CLI.
        """
        try:
            model_id = _validate_model_id(model_id)
        except ValueError as e:
            logger.error(f"unload_model rejected: {e}")
            return False
        logger.info(f"Unloading model: {model_id}")

        unload_success = False
        async def _do_unload_request():
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v0/models/unload",
                    json={"model": model_id},
                    headers=self._headers,
                )
                resp.raise_for_status()  # surface 5xx so _with_retry can retry
                return resp

        try:
            resp = await _with_retry(_do_unload_request, label="unload_model")
            if resp.status_code == 200:
                logger.info(f"Model {model_id} unload requested via REST API")
                unload_success = True
            else:
                logger.warning(f"REST API unload failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"REST API unload failed after retries: {e}")

        if not unload_success:
            logger.info(f"Falling back to CLI for unloading {model_id}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "lms", "unload", model_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    logger.info(f"Model {model_id} unload requested via CLI")
                    unload_success = True
                else:
                    logger.error(f"CLI unload failed: {stderr.decode().strip() if stderr else ''}")
            except Exception as e:
                logger.error(f"CLI unload failed: {e}")
                
        if not unload_success:
            return False
            
        # Verify VRAM reclamation via pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            logger.info(f"pynvml check after unload: {info.free / 1024**2:.0f} MB free VRAM")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pynvml verification failed: {e}")
            
        # Verify unload via /v1/models poll
        for _ in range(5):
            await asyncio.sleep(2.0)
            models = await self.list_models()
            if not any(m.get("id") == model_id for m in models):
                logger.info(f"Verified model {model_id} is unloaded.")
                return True
        logger.error(f"Failed to verify unload of {model_id}")
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

        # SSRF protection: validate the embedding host URL
        from app.services.security import is_safe_base_url
        if not is_safe_base_url(base):
            logger.error("SSRF blocked: unsafe embedding_host %s", base)
            return []

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {"input": texts}
        if embed_model:
            body["model"] = embed_model

        try:
            async def _do_request():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{base}/v1/embeddings",
                        json=body,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                    data_sorted = sorted(data, key=lambda x: x.get("index", 0))
                    return [item["embedding"] for item in data_sorted]
            return await _with_retry(_do_request, label="embed")
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
    ) -> str:
        """Stream chat completion and return the full content string.

        Uses priority semaphore to govern concurrent execution.
        priority: 1 (Retrieval), 2 (Reasoning), 3 (Generation)

        Returns the joined content on success (empty string if the
        model returned zero tokens). Re-raises any exception that
        occurred during the request — callers can ``try/except`` to
        handle the error context, or wrap with ``stream_chat_completion``
        which translates the exception into an ``{"error": ...}`` dict.
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
                        "enable_thinking": True,  # Enable reasoning/thinking mode if supported
                    }
                    if model:
                        body["model"] = model

                    content = []

                    # The coroutine factory below only handles the initial
                    # handshake (open the stream + read response status).
                    # Mid-stream failures are not retried: re-iterating after
                    # partial bytes would duplicate chunks already sent to
                    # the chunk callback.
                    llm_start = time.perf_counter()
                    async def _open_stream():
                        client = httpx.AsyncClient(timeout=120.0)
                        resp_ctx = client.stream(
                            "POST",
                            f"{self.base_url}/v1/chat/completions",
                            json=body,
                            headers=self._headers,
                        )
                        resp = await resp_ctx.__aenter__()
                        try:
                            resp.raise_for_status()
                        except Exception:
                            # Roll back the open response/context cleanly so
                            # the next retry attempt starts fresh.
                            await resp_ctx.__aexit__(None, None, None)
                            await client.aclose()
                            raise
                        return client, resp_ctx, resp

                    client, resp_ctx, resp = await _with_retry(
                        _open_stream, label="stream_chat_open"
                    )
                    try:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    tok = delta.get("content", "")
                                    # Qwen3 thinking mode: also capture reasoning_content
                                    reason_tok = delta.get("reasoning_content", "")
                                    if tok:
                                        content.append(tok)
                                        if chunk_callback:
                                            if asyncio.iscoroutinefunction(chunk_callback):
                                                await chunk_callback(tok)
                                            else:
                                                chunk_callback(tok)
                                    if reason_tok:
                                        if chunk_callback:
                                            if asyncio.iscoroutinefunction(chunk_callback):
                                                await chunk_callback(reason_tok)
                                            else:
                                                chunk_callback(reason_tok)
                                except json.JSONDecodeError:
                                    pass
                    finally:
                        await resp_ctx.__aexit__(None, None, None)
                        await client.aclose()
                    # Record LLM latency for Prometheus
                    llm_elapsed = time.perf_counter() - llm_start
                    try:
                        from app.services.metrics import LLM_LATENCY, LLM_REQUEST_COUNT
                        LLM_LATENCY.labels(method="stream_chat").observe(llm_elapsed)
                        LLM_REQUEST_COUNT.labels(method="stream_chat").inc()
                    except Exception:
                        pass  # metrics import should not crash the pipeline
                    # Empty content (model returned zero tokens) is a
                    # valid result and returned as "". Errors are surfaced
                    # via the future's exception — callers can distinguish
                    # "no answer yet" (empty string) from "request failed"
                    # (raised exception).
                    future.set_result("".join(content))
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

        # Execute directly via task (semaphore inside _execute handles concurrency)
        asyncio.create_task(_execute())
        # Re-raise exceptions to the caller instead of swallowing them
        # as ``None`` — callers that need to handle empty results can
        # check ``if not result`` which works for both ``""`` and ``None``
        # if they really want the distinction.
        return await future

    async def _process_next(self):
        """Worker to process the next item in the priority queue."""
        if not self._queue.empty():
            _, _, func = await self._queue.get()
            await func()
            self._queue.task_done()

