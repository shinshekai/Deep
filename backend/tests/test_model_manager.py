"""Model Manager tests — real services, no mocks."""

import time

import pytest

from app.services.model_manager import ModelManager


@pytest.fixture()
async def mgr(_init_real_state):
    from app.state import lm_client
    mgr = ModelManager(lm_client)
    yield mgr
    # Unload any models loaded during the test to free VRAM
    for model_id in list(mgr._loaded_models.keys()):
        try:
            await lm_client.unload_model(model_id)
        except Exception:
            pass
    mgr._loaded_models.clear()


def test_get_tier_for_model(mgr):
    assert mgr.get_tier_for_model("google/gemma-4-e2b") == 1
    assert mgr.get_tier_for_model("qwen/qwen3.5-9b") == 2
    assert mgr.get_tier_for_model("google/gemma-4-12b") == 3
    assert mgr.get_tier_for_model("Unknown-Model") == 0


@pytest.mark.asyncio
async def test_get_model_for_tier(mgr):
    mgr._loaded_models = {
        "qwen/qwen3.5-9b": {"tier": 2},
        "google/gemma-4-12b": {"tier": 3},
    }
    assert await mgr.get_model_for_tier(2) == "qwen/qwen3.5-9b"
    assert await mgr.get_model_for_tier(3) == "google/gemma-4-12b"
    assert await mgr.get_model_for_tier(1) is None


def test_get_tier_from_complexity(mgr):
    assert mgr.get_tier_from_complexity(0.2) == 1
    assert mgr.get_tier_from_complexity(0.5) == 2
    assert mgr.get_tier_from_complexity(0.8) == 3


def test_check_ttl_evictions(mgr):
    now = time.time()
    mgr._loaded_models = {
        "google/gemma-4-e2b": {"tier": 1, "last_used": now - 10000},
        "qwen/qwen3.5-9b": {"tier": 2, "last_used": now - 700},
        "zai-org/glm-4.7-flash": {"tier": 2, "last_used": now - 100},
        "google/gemma-4-26b-a4b": {"tier": 3, "last_used": now - 400},
    }

    evicted = mgr.check_ttl_evictions()
    assert "qwen/qwen3.5-9b" in evicted
    assert "google/gemma-4-26b-a4b" in evicted
    assert "google/gemma-4-e2b" not in evicted
    assert "zai-org/glm-4.7-flash" not in evicted

    assert "qwen/qwen3.5-9b" not in mgr._loaded_models
    assert "zai-org/glm-4.7-flash" in mgr._loaded_models


@pytest.mark.asyncio
async def test_handle_pressure_red(mgr):
    mgr._loaded_models = {
        "google/gemma-4-e2b": {"tier": 1},
        "qwen/qwen3.5-9b": {"tier": 2},
        "google/gemma-4-12b": {"tier": 3},
    }

    await mgr.handle_pressure("red")

    assert "google/gemma-4-e2b" in mgr._loaded_models
    assert "qwen/qwen3.5-9b" not in mgr._loaded_models
    assert "google/gemma-4-12b" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_get_best_available_model(mgr):
    mgr._loaded_models = {
        "google/gemma-4-12b": {"tier": 3},
        "qwen/qwen3.5-9b": {"tier": 2},
        "google/gemma-4-e2b": {"tier": 1},
    }

    assert await mgr.get_best_available_model() == "google/gemma-4-e2b"


@pytest.mark.asyncio
async def test_get_best_available_model_prefers_active_selection(mgr):
    mgr._loaded_models = {
        "google/gemma-4-12b": {"tier": 3},
        "qwen/qwen3.5-9b": {"tier": 2},
    }
    mgr.set_active_selection("local", "lm_studio", "qwen/qwen3.5-9b")

    assert await mgr.get_best_available_model(2) == "qwen/qwen3.5-9b"


@pytest.mark.asyncio
async def test_get_model_for_tier_uses_active_selection(mgr):
    mgr._settings.turboquant_enabled = False
    mgr.set_active_selection("local", "lm_studio", "qwen/qwen3.5-9b")

    result = await mgr.get_model_for_tier(3)
    assert result == "qwen/qwen3.5-9b"
    assert "google/gemma-4-12b" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_get_best_available_model_loads_from_fallback(mgr):
    mgr._loaded_models = {}
    result = await mgr.get_best_available_model()
    assert result is not None
    assert result in mgr._loaded_models


def test_loaded_models_property(mgr):
    mgr._loaded_models = {"test_model": {"tier": 1}}
    lm = mgr.loaded_models
    assert len(lm) == 1
    assert "test_model" in lm


def test_get_kv_config(mgr):
    mgr._settings.turboquant_enabled = False

    assert mgr.get_kv_config(1) == {"cache_type_k": "q8_0", "cache_type_v": "q8_0"}
    assert mgr.get_kv_config(99) == {"cache_type_k": "q8_0", "cache_type_v": "q8_0"}

    mgr._settings.turboquant_enabled = True
    mgr._settings.turboquant_bits = 4
    mgr._settings.turboquant_tier = "auto"
    assert mgr.get_kv_config(1) == {"cache_type_k": "q8_0", "cache_type_v": "turbo4"}


def test_on_query_start(mgr):
    mgr._loaded_models = {"test_model": {"tier": 1, "last_used": 0}}
    mgr.on_query_start("test_model")
    assert mgr._loaded_models["test_model"]["last_used"] > 0

    mgr.on_query_start("unknown")
    assert "unknown" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_handle_pressure_orange_yellow(mgr):
    mgr._loaded_models = {
        "google/gemma-4-e2b": {"tier": 1},
        "qwen/qwen3.5-9b": {"tier": 2},
        "google/gemma-4-12b": {"tier": 3},
    }

    await mgr.handle_pressure("yellow")
    assert "google/gemma-4-12b" in mgr._loaded_models

    await mgr.handle_pressure("orange")
    assert "google/gemma-4-e2b" in mgr._loaded_models
    assert "qwen/qwen3.5-9b" in mgr._loaded_models
    assert "google/gemma-4-12b" not in mgr._loaded_models


def test_get_status(mgr):
    mgr._loaded_models = {
        "google/gemma-4-e2b": {"tier": 1, "vram_mb": 1500},
    }
    status = mgr.get_status()
    assert len(status) > 0

    gemma_info = next((s for s in status if s["id"] == "google/gemma-4-e2b"), None)
    assert gemma_info is not None
    assert gemma_info["status"] == "loaded"
    assert gemma_info["vram_used_mb"] == 1500

    deepseek_info = next(
        (s for s in status if s["id"] == "google/gemma-4-12b"), None
    )
    assert deepseek_info is not None
    assert deepseek_info["status"] == "unloaded"


@pytest.mark.asyncio
async def test_independent_tier_selections(mgr):
    mgr.set_active_selection("T1", "local", "lm_studio", "google/gemma-4-e2b")
    mgr.set_active_selection("T2", "local", "lm_studio", "qwen/qwen3.5-9b")
    mgr.set_active_selection("T3", "local", "lm_studio", "google/gemma-4-12b")

    selections = mgr.get_active_selections()
    assert selections["T1"]["model_id"] == "google/gemma-4-e2b"
    assert selections["T2"]["model_id"] == "qwen/qwen3.5-9b"
    assert selections["T3"]["model_id"] == "google/gemma-4-12b"

    # Verify selection state without triggering real model loads
    assert mgr.get_active_selection() == selections["T3"]

    mgr.clear_active_selection("T2")
    selections = mgr.get_active_selections()
    assert selections["T1"] is not None
    assert selections["T2"] is None
    assert selections["T3"] is not None
