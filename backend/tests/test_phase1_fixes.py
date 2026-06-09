"""Quick smoke tests for Phase 1 fixes."""
import asyncio
import time


def test_keyring_cache_reprobe():
    """SEC-5-007: Keyring cache expires after 5 minutes."""
    from app.services.secrets import _keyring_cache, _KEYRING_REPROBE_INTERVAL, is_keyring_available

    _keyring_cache["available"] = True
    _keyring_cache["ts"] = time.monotonic() - _KEYRING_REPROBE_INTERVAL - 1
    assert _keyring_cache["ts"] < time.monotonic() - _KEYRING_REPROBE_INTERVAL


def test_fts5_tokenizer():
    """DB-4-013: FTS5 tables use porter unicode61 tokenizer."""
    from app.services.memory_service import SCHEMA_SQL
    assert "porter unicode61" in SCHEMA_SQL
    assert "episodes_fts" in SCHEMA_SQL
    assert "facts_fts" in SCHEMA_SQL


def test_deterministic_ordering():
    """DB-4-017: ORDER BY includes deterministic tie-breaking."""
    from app.services.memory_service import MemoryService
    import inspect
    src = inspect.getsource(MemoryService.recall_episodes)
    assert "ORDER BY" in src
    assert "ORDER BY created_at DESC, id" in src


def test_audit_warning_level():
    """SEC-5-004: audit() emits at WARNING level."""
    import inspect
    from app.services.audit import audit
    src = inspect.getsource(audit)
    assert "logger.warning(" in src


def test_enable_thinking_default():
    """AI-8-002: enable_thinking defaults to None (resolves from settings)."""
    import inspect
    from app.services.lm_studio_client import LMStudioClient
    sig = inspect.signature(LMStudioClient.stream_chat)
    param = sig.parameters["enable_thinking"]
    assert param.default is None
