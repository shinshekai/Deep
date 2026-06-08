"""LLM response cache — SHA-256 key + diskcache persistence.

Avoids redundant LLM calls for identical requests. Uses a content-addressable
cache keyed on the SHA-256 hash of (model, messages, temperature, max_tokens).
"""

import hashlib
import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "llm_responses"
_DEFAULT_TTL = 3600
_MAX_ENTRIES = 1000


class ResponseCache:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
        ttl: int = _DEFAULT_TTL,
        max_entries: int = _MAX_ENTRIES,
    ):
        self._cache_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self._ttl = ttl
        self._max_entries = max_entries
        self._disk_cache = None

    def _get_cache(self):
        if self._disk_cache is None:
            try:
                import diskcache

                self._cache_dir.mkdir(parents=True, exist_ok=True)
                self._disk_cache = diskcache.Cache(
                    str(self._cache_dir),
                    disk_pickle_protocol=5,
                )
                logger.debug("Response cache initialized at %s", self._cache_dir)
            except Exception as e:
                logger.warning("diskcache unavailable, response caching disabled: %s", e)
                self._disk_cache = False
        return self._disk_cache

    @staticmethod
    def _make_key(
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(
        self, model: str, messages: list[dict], temperature: float, max_tokens: int
    ) -> str | None:
        cache = self._get_cache()
        if not cache:
            return None
        key = self._make_key(model, messages, temperature, max_tokens)
        try:
            entry = cache.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                cache.delete(key)
                return None
            return value
        except Exception:
            return None

    def set(
        self, model: str, messages: list[dict], temperature: float, max_tokens: int, response: str
    ) -> None:
        cache = self._get_cache()
        if not cache:
            return
        key = self._make_key(model, messages, temperature, max_tokens)
        try:
            cache.set(key, (response, time.time()), expire=self._ttl)
        except Exception as e:
            logger.debug("Response cache set failed: %s", e)

    def stats(self) -> dict:
        cache = self._get_cache()
        if not cache:
            return {"enabled": False}
        try:
            return {"enabled": True, "entries": len(cache), "directory": str(self._cache_dir)}
        except Exception:
            return {"enabled": True, "entries": -1}


_cache: ResponseCache | None = None
_cache_lock = threading.Lock()


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = ResponseCache()
    return _cache
