"""Model Manager — three-tier lifecycle with TTL-based unloading and fallback cascade.

Tier 1 (Always Resident): liquid/lfm2.5-1.2b, jinaai.readerlm-v2/jinaai.ReaderLM-v2.f16.gguf — VRAM 1-3.5 GB
Tier 2 (Semi-Resident):   nvidia/nemotron-3-nano-4b, deepseek/deepseek-r1-0528-qwen3-8b   — VRAM 4-9.5 GB, TTL 600s
Tier 3 (On-Demand):       google/gemma-4-26b-a4b, qwen/qwen3.6-35b-a3b    — VRAM 25-40 GB, TTL 300s
"""

import asyncio
import logging
import time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Fallback cascade (CLAUDE.md Section 6.3)
FALLBACK_CASCADE = [
    "qwen/qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "nvidia/nemotron-3-nano-4b",
    "jinaai.readerlm-v2/jinaai.ReaderLM-v2.f16.gguf",
    "liquid/lfm2.5-1.2b",
]

TTL_DEFAULTS = {
    1: float("inf"),  # Always resident
    2: 600,
    3: 300,
}

MODEL_TIERS = {
    # tier -> (models, vram_range_mb, kv_config, max_concurrent)
    1: {
        "models": ["liquid/lfm2.5-1.2b", "jinaai.readerlm-v2/jinaai.ReaderLM-v2.f16.gguf"],
        "vram_range": (1000, 3500),
        "kv_cache": {"cache_type_k": "q4_0", "cache_type_v": "q4_0"},
        "max_concurrent": 4,
    },
    2: {
        "models": ["nvidia/nemotron-3-nano-4b", "deepseek/deepseek-r1-0528-qwen3-8b"],
        "vram_range": (4000, 9500),
        "kv_cache": {"cache_type_k": "q8_0", "cache_type_v": "q4_0"},
        "max_concurrent": 2,
    },
    3: {
        "models": ["google/gemma-4-26b-a4b", "qwen/qwen3.6-35b-a3b"],
        "vram_range": (25000, 40000),
        "kv_cache": {"cache_type_k": "q8_0", "cache_type_v": "q8_0"},
        "max_concurrent": 1,
    },
}


class ModelManager:
    """Manage model lifecycle: loading, unloading, fallback under VRAM pressure."""

    def __init__(self, lm_client):
        self.lm_client = lm_client
        self._loaded_models: dict = {}  # model_id -> {tier, loaded_at, last_used}
        self._settings = get_settings()

    @property
    def loaded_models(self) -> dict:
        return dict(self._loaded_models)

    async def get_model_for_tier(self, tier: int) -> Optional[str]:
        """Return the first available model for the given tier, loading it if necessary."""
        candidates = MODEL_TIERS.get(tier, {}).get("models", [])
        for model_id in candidates:
            if model_id in self._loaded_models:
                return model_id
        
        # None loaded, try to load the first candidate
        if candidates:
            target_model = candidates[0]
            kv_config = self.get_kv_config(tier)
            success = await self.lm_client.load_model(
                target_model, 
                cache_type_k=kv_config.get("cache_type_k"),
                cache_type_v=kv_config.get("cache_type_v")
            )
            if success:
                self._loaded_models[target_model] = {"tier": tier, "loaded_at": time.time(), "last_used": time.time()}
                return target_model
        return None

    def get_tier_for_model(self, model_id: str) -> int:
        for tier, info in MODEL_TIERS.items():
            if model_id in info["models"]:
                return tier
        return 0

    def get_kv_config(self, tier: int) -> dict:
        """Get KV config based on tier and global TurboQuant settings."""
        # Baseline from static tiers
        base_config = dict(MODEL_TIERS.get(tier, {}).get("kv_cache", {"cache_type_k": "q8_0", "cache_type_v": "q8_0"}))
        
        if self._settings.turboquant_enabled:
            bits = self._settings.turboquant_bits
            # Recommendation: asymmetric is safest for general models (q8_0 K, turbo V)
            turbo_type = f"turbo{bits}"
            
            # Optionally check turboquant_tier setting
            if self._settings.turboquant_tier == "auto" or str(tier) == self._settings.turboquant_tier:
                base_config["cache_type_k"] = "q8_0"
                base_config["cache_type_v"] = turbo_type
                
        return base_config

    def get_tier_from_complexity(self, score: float) -> int:
        """Decide tier from complexity score."""
        if score < 0.3:
            return 1
        elif score < 0.6:
            return 2
        return 3

    async def get_best_available_model(self) -> Optional[str]:
        """Get best model considering VRAM pressure. Used for fallback cascade."""
        for model_id in FALLBACK_CASCADE:
            if model_id in self._loaded_models:
                return model_id
                
        # If nothing loaded, try to load from cascade
        for model_id in FALLBACK_CASCADE:
            tier = self.get_tier_for_model(model_id)
            kv_config = self.get_kv_config(tier)
            success = await self.lm_client.load_model(
                model_id,
                cache_type_k=kv_config.get("cache_type_k"),
                cache_type_v=kv_config.get("cache_type_v")
            )
            if success:
                self._loaded_models[model_id] = {"tier": tier, "loaded_at": time.time(), "last_used": time.time()}
                return model_id
        return None

    def on_query_start(self, model_id: str):
        """Update last_used timestamp for TTL tracking."""
        if model_id in self._loaded_models:
            self._loaded_models[model_id]["last_used"] = time.time()

    def check_ttl_evictions(self) -> list[str]:
        """Evict models that have exceeded their TTL. Returns evicted model IDs."""
        evicted = []
        now = time.time()
        settings = get_settings()

        for model_id, info in list(self._loaded_models.items()):
            tier = info["tier"]
            ttl = TTL_DEFAULTS.get(tier, 600)
            if tier == 2:
                ttl = settings.t2_ttl if hasattr(settings, 't2_ttl') else 600
            elif tier == 3:
                ttl = settings.t3_ttl if hasattr(settings, 't3_ttl') else 300

            if ttl == float("inf"):
                continue

            elapsed = now - info["last_used"]
            if elapsed > ttl:
                evicted.append(model_id)
                del self._loaded_models[model_id]
                logger.info(f"TTL evict: {model_id} (idle {elapsed:.0f}s > {ttl}s)")

        return evicted

    async def handle_pressure(self, pressure_level: str):
        """React to VRAM pressure changes per CLAUDE.md Section 7."""
        if pressure_level == "yellow":
            # Downgrade T3 KV cache, reduce T2 context by 50%
            logger.info("YELLOW pressure: downgrading T3 KV cache")
            t3_models = [mid for mid, info in self._loaded_models.items() if info["tier"] == 3]
            for mid in t3_models:
                logger.info(f"Reloading {mid} with downgraded KV cache")
                await self.lm_client.unload_model(mid)
                # Determine downgraded config
                kv_config = self.get_kv_config(3)
                kv_config["cache_type_v"] = "q4_0" # Downgrade V cache
                if self._settings.turboquant_enabled:
                    kv_config["cache_type_v"] = "turbo2" # Max compression
                await self.lm_client.load_model(
                    mid,
                    cache_type_k=kv_config.get("cache_type_k"),
                    cache_type_v=kv_config.get("cache_type_v")
                )
                self._loaded_models[mid]["last_used"] = time.time()
                
        elif pressure_level == "orange":
            # Unload T3 models, route to T2
            to_remove = [
                mid for mid, info in self._loaded_models.items()
                if info["tier"] == 3
            ]
            for mid in to_remove:
                await self.lm_client.unload_model(mid)
                del self._loaded_models[mid]
                logger.info(f"ORANGE pressure: unloaded T3 model {mid}")
        elif pressure_level == "red":
            # Emergency: unload T2, T1-only with 2K truncation
            to_remove = [
                mid for mid, info in self._loaded_models.items()
                if info["tier"] in (2, 3)
            ]
            for mid in to_remove:
                await self.lm_client.unload_model(mid)
                del self._loaded_models[mid]
                logger.info(f"RED pressure: unloaded {mid}")

    def get_status(self) -> list[dict]:
        """Return status of all known tiers and loaded models."""
        result = []
        for tier, info in MODEL_TIERS.items():
            for model_id in info["models"]:
                is_loaded = model_id in self._loaded_models
                loaded_info = self._loaded_models.get(model_id, {})
                result.append({
                    "id": model_id,
                    "name": model_id,
                    "tier": tier,
                    "status": "loaded" if is_loaded else "unloaded",
                    "vram_used_mb": loaded_info.get("vram_mb", 0),
                    "kv_cache_config": info["kv_cache"],
                    "max_concurrent": info["max_concurrent"],
                })
        return result
