"""Model Manager tests."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.model_manager import ModelManager


def test_get_tier_for_model():
    mgr = ModelManager(MagicMock())
    assert mgr.get_tier_for_model("liquid/lfm2.5-1.2b") == 1
    assert mgr.get_tier_for_model("deepseek/deepseek-r1-0528-qwen3-8b") == 2
    assert mgr.get_tier_for_model("qwen/qwen3.6-35b-a3b") == 3
    assert mgr.get_tier_for_model("Unknown-Model") == 0


@pytest.mark.asyncio
async def test_get_model_for_tier():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.load_model = AsyncMock(return_value=False)
    mgr._loaded_models = {
        "nvidia/nemotron-3-nano-4b": {"tier": 2},
        "qwen/qwen3.6-35b-a3b": {"tier": 3},
    }
    assert await mgr.get_model_for_tier(2) == "nvidia/nemotron-3-nano-4b"
    assert await mgr.get_model_for_tier(3) == "qwen/qwen3.6-35b-a3b"
    assert await mgr.get_model_for_tier(1) is None


def test_get_tier_from_complexity():
    mgr = ModelManager(MagicMock())
    assert mgr.get_tier_from_complexity(0.2) == 1
    assert mgr.get_tier_from_complexity(0.5) == 2
    assert mgr.get_tier_from_complexity(0.8) == 3


def test_check_ttl_evictions():
    mgr = ModelManager(MagicMock())
    now = time.time()
    mgr._loaded_models = {
        "liquid/lfm2.5-1.2b": {"tier": 1, "last_used": now - 10000},  # Never evict Tier 1
        "deepseek/deepseek-r1-0528-qwen3-8b": {"tier": 2, "last_used": now - 700},  # TTL is 600
        "nvidia/nemotron-3-nano-4b": {"tier": 2, "last_used": now - 100},  # Keep
        "google/gemma-4-26b-a4b": {"tier": 3, "last_used": now - 400},  # TTL is 300
    }

    evicted = mgr.check_ttl_evictions()
    assert "deepseek/deepseek-r1-0528-qwen3-8b" in evicted
    assert "google/gemma-4-26b-a4b" in evicted
    assert "liquid/lfm2.5-1.2b" not in evicted
    assert "nvidia/nemotron-3-nano-4b" not in evicted

    # Check they were removed
    assert "deepseek/deepseek-r1-0528-qwen3-8b" not in mgr._loaded_models
    assert "nvidia/nemotron-3-nano-4b" in mgr._loaded_models


@pytest.mark.asyncio
async def test_handle_pressure_red():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.unload_model = AsyncMock()
    mgr._loaded_models = {
        "liquid/lfm2.5-1.2b": {"tier": 1},
        "deepseek/deepseek-r1-0528-qwen3-8b": {"tier": 2},
        "qwen/qwen3.6-35b-a3b": {"tier": 3},
    }

    await mgr.handle_pressure("red")

    # Under RED pressure, T2 and T3 should be unloaded
    assert "liquid/lfm2.5-1.2b" in mgr._loaded_models
    assert "deepseek/deepseek-r1-0528-qwen3-8b" not in mgr._loaded_models
    assert "qwen/qwen3.6-35b-a3b" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_get_best_available_model():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {
        "qwen/qwen3.6-35b-a3b": {"tier": 3},
        "nvidia/nemotron-3-nano-4b": {"tier": 2},
        "liquid/lfm2.5-1.2b": {"tier": 1},
    }

    # Safety default: without explicit selection, prefer the smallest loaded model.
    assert await mgr.get_best_available_model() == "liquid/lfm2.5-1.2b"


@pytest.mark.asyncio
async def test_get_best_available_model_prefers_active_selection():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.load_model = AsyncMock(return_value=True)
    mgr._loaded_models = {
        "qwen/qwen3.6-35b-a3b": {"tier": 3},
        "nvidia/nemotron-3-nano-4b": {"tier": 2},
    }
    mgr.set_active_selection("local", "lm_studio", "nvidia/nemotron-3-nano-4b")

    assert await mgr.get_best_available_model(2) == "nvidia/nemotron-3-nano-4b"


@pytest.mark.asyncio
async def test_get_model_for_tier_uses_active_selection_instead_of_auto_loading_t3():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.load_model = AsyncMock(return_value=True)
    mgr.set_active_selection("local", "lm_studio", "nvidia/nemotron-3-nano-4b")

    assert await mgr.get_model_for_tier(3) == "nvidia/nemotron-3-nano-4b"
    mgr.lm_client.load_model.assert_called_once_with(
        "nvidia/nemotron-3-nano-4b",
        cache_type_k="q8_0",
        cache_type_v="turbo4",
    )
    assert "qwen/qwen3.6-35b-a3b" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_get_best_available_model_none():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {}

    # Needs a mock for lm_client.load_model to return False so it returns None
    mgr.lm_client.load_model = AsyncMock(return_value=False)

    assert await mgr.get_best_available_model() is None


def test_loaded_models_property():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {"test_model": {"tier": 1}}
    lm = mgr.loaded_models
    assert len(lm) == 1
    assert "test_model" in lm


def test_get_kv_config():
    mgr = ModelManager(MagicMock())
    mgr._settings.turboquant_enabled = False

    assert mgr.get_kv_config(1) == {"cache_type_k": "q4_0", "cache_type_v": "q4_0"}
    assert mgr.get_kv_config(99) == {"cache_type_k": "q8_0", "cache_type_v": "q8_0"}

    # Test turboquant enabled
    mgr._settings.turboquant_enabled = True
    mgr._settings.turboquant_bits = 4
    mgr._settings.turboquant_tier = "auto"
    assert mgr.get_kv_config(1) == {"cache_type_k": "q8_0", "cache_type_v": "turbo4"}


def test_on_query_start():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {"test_model": {"tier": 1, "last_used": 0}}
    mgr.on_query_start("test_model")
    assert mgr._loaded_models["test_model"]["last_used"] > 0

    # Non existent model
    mgr.on_query_start("unknown")
    assert "unknown" not in mgr._loaded_models


@pytest.mark.asyncio
async def test_handle_pressure_orange_yellow():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.unload_model = AsyncMock()
    mgr.lm_client.load_model = AsyncMock(return_value=True)
    mgr._loaded_models = {
        "liquid/lfm2.5-1.2b": {"tier": 1},
        "deepseek/deepseek-r1-0528-qwen3-8b": {"tier": 2},
        "qwen/qwen3.6-35b-a3b": {"tier": 3},
    }

    await mgr.handle_pressure("yellow")
    # No unloading happens in yellow
    assert "qwen/qwen3.6-35b-a3b" in mgr._loaded_models

    await mgr.handle_pressure("orange")
    # T3 is unloaded
    assert "liquid/lfm2.5-1.2b" in mgr._loaded_models
    assert "deepseek/deepseek-r1-0528-qwen3-8b" in mgr._loaded_models
    assert "qwen/qwen3.6-35b-a3b" not in mgr._loaded_models


def test_get_status():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {
        "liquid/lfm2.5-1.2b": {"tier": 1, "vram_mb": 1500},
    }
    status = mgr.get_status()
    assert len(status) > 0
    # Check that liquid is marked as loaded
    liquid_info = next((s for s in status if s["id"] == "liquid/lfm2.5-1.2b"), None)
    assert liquid_info is not None
    assert liquid_info["status"] == "loaded"
    assert liquid_info["vram_used_mb"] == 1500

    # Check another model is unloaded
    deepseek_info = next(
        (s for s in status if s["id"] == "deepseek/deepseek-r1-0528-qwen3-8b"), None
    )
    assert deepseek_info is not None
    assert deepseek_info["status"] == "unloaded"


@pytest.mark.asyncio
async def test_independent_tier_selections():
    mgr = ModelManager(MagicMock())
    mgr.lm_client.load_model = AsyncMock(return_value=True)

    # Set separate selections for each tier
    mgr.set_active_selection("T1", "local", "lm_studio", "liquid/lfm2.5-1.2b")
    mgr.set_active_selection("T2", "local", "lm_studio", "nvidia/nemotron-3-nano-4b")
    mgr.set_active_selection("T3", "local", "lm_studio", "qwen/qwen3.6-35b-a3b")

    selections = mgr.get_active_selections()
    assert selections["T1"]["model_id"] == "liquid/lfm2.5-1.2b"
    assert selections["T2"]["model_id"] == "nvidia/nemotron-3-nano-4b"
    assert selections["T3"]["model_id"] == "qwen/qwen3.6-35b-a3b"

    # Verify that get_model_for_tier resolves the correct model
    assert await mgr.get_model_for_tier(1) == "liquid/lfm2.5-1.2b"
    assert await mgr.get_model_for_tier(2) == "nvidia/nemotron-3-nano-4b"
    assert await mgr.get_model_for_tier(3) == "qwen/qwen3.6-35b-a3b"

    # Clear T2 selection and check
    mgr.clear_active_selection("T2")
    selections = mgr.get_active_selections()
    assert selections["T1"] is not None
    assert selections["T2"] is None
    assert selections["T3"] is not None
