"""Model Manager — three-tier lifecycle with TTL-based unloading and fallback cascade.

Tier 1 (Always Resident): Qwen3-0.6B, Qwen3-1.7B — VRAM 0.5-1.2 GB
Tier 2 (Semi-Resident):   Qwen3-4B, Qwen3-8B   — VRAM 2.5-5.5 GB, TTL 600s
Tier 3 (On-Demand):       Qwen3-14B, 30B-A3B    — VRAM 8.5-18 GB, TTL 300s
"""

import asyncio
import logging
import time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Fallback cascade (CLAUDE.md Section 6.3)
FALLBACK_CASCADE = [
    "Qwen3-30B-A3B-Q4_K_M",
    "Qwen3-14B-Q4_K_M",
    "Qwen3-8B-Q5_K_M",
    "Qwen3-4B-Q4_K_M",
    "Qwen3-1.7B-Q4_K_M",
    "Qwen3-0.6B-Q4_K_M",
]

TTL_DEFAULTS = {
    1: float("inf"),  # Always resident
    2: 600,
    3: 300,
}

MODEL_TIERS = {
    # tier -> (models, vram_range_mb, kv_config, max_concurrent)
    1: {
        "models": ["Qwen3-0.6B-Q4_K_M", "Qwen3-1.7B-Q4_K_M"],
        "vram_range": (500, 1200),
        "kv_cache": {"cache_type_k": "q4_0", "cache_type_v": "q4_0"},
        "max_concurrent": 4,
    },
    2: {
        "models": ["Qwen3-4B-Q4_K_M", "Qwen3-8B-Q5_K_M"],
        "vram_range": (2500, 5500),
        "kv_cache": {"cache_type_k": "q8_0", "cache_type_v": "q4_0"},
        "max_concurrent": 2,
    },
    3: {
        "models": ["Qwen3-14B-Q4_K_M", "Qwen3-30B-A3B-Q4_K_M"],
        "vram_range": (8500, 18000),
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

    def get_model_for_tier(self, tier: int) -> Optional[str]:
        """Return the first available model for the given tier."""
        candidates = MODEL_TIERS.get(tier, {}).get("models", [])
        for model_id in candidates:
            if model_id in self._loaded_models:
                return model_id
        return None

    def get_tier_for_model(self, model_id: str) -> int:
        for tier, info in MODEL_TIERS.items():
            if model_id in info["models"]:
                return tier
        return 0

    def get_kv_config(self, tier: int) -> dict:
        return MODEL_TIERS.get(tier, {}).get("kv_cache", {})

    def get_tier_from_complexity(self, score: float) -> int:
        """Decide tier from complexity score."""
        if score < 0.3:
            return 1
        elif score < 0.6:
            return 2
        return 3

    def get_best_available_model(self) -> Optional[str]:
        """Get best model considering VRAM pressure. Used for fallback cascade."""
        for model_id in FALLBACK_CASCADE:
            if model_id in self._loaded_models:
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
        elif pressure_level == "orange":
            # Unload T3 models, route to T2
            to_remove = [
                mid for mid, info in self._loaded_models.items()
                if info["tier"] == 3
            ]
            for mid in to_remove:
                del self._loaded_models[mid]
                logger.info(f"ORANGE pressure: unloaded T3 model {mid}")
        elif pressure_level == "red":
            # Emergency: unload T2, T1-only with 2K truncation
            to_remove = [
                mid for mid, info in self._loaded_models.items()
                if info["tier"] in (2, 3)
            ]
            for mid in to_remove:
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
