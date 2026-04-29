"""Model Manager tests."""

import time
import pytest
from unittest.mock import MagicMock

from app.services.model_manager import ModelManager, MODEL_TIERS, FALLBACK_CASCADE

def test_get_tier_for_model():
    mgr = ModelManager(MagicMock())
    assert mgr.get_tier_for_model("liquid/lfm2.5-1.2b") == 1
    assert mgr.get_tier_for_model("deepseek/deepseek-r1-0528-qwen3-8b") == 2
    assert mgr.get_tier_for_model("qwen/qwen3.6-35b-a3b") == 3
    assert mgr.get_tier_for_model("Unknown-Model") == 0

def test_get_model_for_tier():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {
        "nvidia/nemotron-3-nano-4b": {"tier": 2},
        "qwen/qwen3.6-35b-a3b": {"tier": 3}
    }
    assert mgr.get_model_for_tier(2) == "nvidia/nemotron-3-nano-4b"
    assert mgr.get_model_for_tier(3) == "qwen/qwen3.6-35b-a3b"
    assert mgr.get_model_for_tier(1) is None

def test_get_tier_from_complexity():
    mgr = ModelManager(MagicMock())
    assert mgr.get_tier_from_complexity(0.2) == 1
    assert mgr.get_tier_from_complexity(0.5) == 2
    assert mgr.get_tier_from_complexity(0.8) == 3

def test_check_ttl_evictions():
    mgr = ModelManager(MagicMock())
    now = time.time()
    mgr._loaded_models = {
        "liquid/lfm2.5-1.2b": {"tier": 1, "last_used": now - 10000}, # Never evict Tier 1
        "deepseek/deepseek-r1-0528-qwen3-8b": {"tier": 2, "last_used": now - 700},    # TTL is 600
        "nvidia/nemotron-3-nano-4b": {"tier": 2, "last_used": now - 100},    # Keep
        "google/gemma-4-26b-a4b": {"tier": 3, "last_used": now - 400},   # TTL is 300
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

def test_get_best_available_model():
    mgr = ModelManager(MagicMock())
    mgr._loaded_models = {
        "nvidia/nemotron-3-nano-4b": {"tier": 2},
        "liquid/lfm2.5-1.2b": {"tier": 1},
    }
    
    # From FALLBACK_CASCADE, the best one loaded should be nvidia/nemotron-3-nano-4b
    assert mgr.get_best_available_model() == "nvidia/nemotron-3-nano-4b"
