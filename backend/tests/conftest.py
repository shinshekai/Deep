"""Shared pytest fixtures for UDIP backend tests.

Patches app.state in-place for every test so routers that import state at
module scope see mock services instead of None.
"""

import os

# Disable auth in tests by setting token to empty — the middleware
# only enforces auth ``if token:`` (truthy check).
os.environ["WS_AUTH_TOKEN"] = ""
# Allow local LLM connections in tests (SSRF guard blocks localhost otherwise)
os.environ["UDIP_ALLOW_LOCAL_LLM"] = "1"
# Clear cached settings so the new env vars take effect
from app.config import get_settings

get_settings.cache_clear()
# Also patch the module-level settings object in main.py so the
# middleware sees the empty token (settings was already created at import time).
import app.main as _main

_main.settings.ws_auth_token = ""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _build_mock_services():
    """Build mock service objects for all state.* attributes."""
    lm = MagicMock()
    lm.check_health = AsyncMock(return_value=True)
    lm.list_models = AsyncMock(return_value=[])
    lm.embed = AsyncMock(return_value=[[0.0] * 384])
    lm.stream_chat = AsyncMock(return_value="Mock response")
    lm.stream_chat_completion = AsyncMock(return_value={"content": "Mock response"})
    lm.load_model = AsyncMock(return_value=True)
    lm.unload_model = AsyncMock(return_value=True)

    vm = MagicMock()
    vm.poll_once = AsyncMock(
        return_value={
            "vram_total_mb": 16000,
            "vram_used_mb": 8000,
            "vram_used_pct": 50.0,
            "pressure_level": "green",
            "gpu_available": True,
        }
    )
    vm.is_active = True

    mm = MagicMock()
    mm._loaded_models = {}
    mm.get_tier_for_model = MagicMock(return_value=1)
    mm.get_model_for_tier = AsyncMock(return_value="mock-model")
    mm.get_best_available_model = AsyncMock(return_value="mock-model")
    mm.get_tier_from_complexity = MagicMock(return_value=1)
    mm.get_kv_config = MagicMock(return_value={"cache_type_k": "q4_0", "cache_type_v": "q4_0"})
    mm.check_ttl_evictions = MagicMock(return_value=[])
    mm.get_status = MagicMock(return_value=[])
    mm.get_active_selection = MagicMock(return_value=None)

    def mock_set_active_selection(*args):
        if len(args) == 4:
            tier, provider_type, provider_id, model_id = args
        else:
            provider_type, provider_id, model_id = args
            tier = "T3"
        return {
            "provider_type": provider_type,
            "provider_id": provider_id,
            "model_id": model_id,
            "selected_at": 1.0,
        }

    mm.set_active_selection = MagicMock(side_effect=mock_set_active_selection)
    mm.get_active_selections = MagicMock(return_value={"T1": None, "T2": None, "T3": None})

    md = MagicMock()
    md.discover = AsyncMock(return_value={"local": [], "cloud": [], "active_selection": None})

    pig = MagicMock()
    pig.generate_index = AsyncMock(return_value={"root": {}})

    emb = MagicMock()
    emb.embed = AsyncMock(return_value=[[0.0] * 384])

    tc = MagicMock()
    tc.chunk = MagicMock(return_value=[])

    vkb = MagicMock()
    vkb.search = AsyncMock(return_value=[])
    vkb.hybrid_search = AsyncMock(return_value=[])
    vkb.naive_search = AsyncMock(return_value=[])
    vkb.get_stats = MagicMock(return_value={"total_chunks": 0, "total_size_mb": 0})
    vkb.build_index = AsyncMock()

    dr = MagicMock()
    dr.start_research = AsyncMock(return_value="mock-session-id")
    dr.get_status = MagicMock(return_value={"status": "COMPLETED", "final_report": "Mock report"})

    bm = MagicMock()
    bm.start_run = AsyncMock(return_value="mock-run-id")
    bm.get_run = MagicMock(return_value=None)
    bm.get_latest_run = MagicMock(return_value=None)
    bm.start_worker = AsyncMock()

    return lm, vm, mm, md, pig, emb, tc, vkb, dr, bm


# Build mocks once per session
_lm, _vm, _mm, _md, _pig, _emb, _tc, _vkb, _dr, _bm = _build_mock_services()


@pytest.fixture(autouse=True)
def mock_state():
    """Patch state.* attributes in-place so existing router references see mocks."""
    import app.state as state_module

    # Save originals
    originals = {}
    targets = {
        "lm_client": _lm,
        "vram_monitor": _vm,
        "model_manager": _mm,
        "model_discovery": _md,
        "pageindex_generator": _pig,
        "embedding_service": _emb,
        "text_chunker": _tc,
        "vector_kb_service": _vkb,
        "deep_research_service": _dr,
        "benchmark_runner": _bm,
    }
    for name, mock in targets.items():
        originals[name] = getattr(state_module, name, None)
        setattr(state_module, name, mock)

    # Reset mutable state between tests
    _mm._loaded_models = {}

    yield state_module

    # Restore originals
    for name, orig in originals.items():
        setattr(state_module, name, orig)


@pytest.fixture
def mock_lm():
    return _lm


@pytest.fixture
def mock_vm():
    return _vm


@pytest.fixture
def mock_mm():
    return _mm


@pytest.fixture
def mock_model_discovery():
    return _md


@pytest.fixture
def mock_dr():
    return _dr
