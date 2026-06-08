"""Model Manager — three-tier lifecycle with TTL-based unloading and fallback cascade.

Tier 1 (Always Resident): liquid/lfm2.5-1.2b, jinaai.readerlm-v2/jinaai.ReaderLM-v2.f16.gguf — VRAM 1-3.5 GB
Tier 2 (Semi-Resident):   nvidia/nemotron-3-nano-4b, deepseek/deepseek-r1-0528-qwen3-8b   — VRAM 4-9.5 GB, TTL 600s
Tier 3 (On-Demand):       google/gemma-4-26b-a4b, qwen/qwen3.6-35b-a3b    — VRAM 25-40 GB, TTL 300s
"""

import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)

# Historical capability-first cascade. Do not use for implicit selection.
FALLBACK_CASCADE = [
    "qwen/qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "nvidia/nemotron-3-nano-4b",
    "jinaai.readerlm-v2/jinaai.ReaderLM-v2.f16.gguf",
    "liquid/lfm2.5-1.2b",
]

# Safety-first fallback for laptop/consumer hardware.
SAFE_FALLBACK_CASCADE = list(reversed(FALLBACK_CASCADE))

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
        self._active_selections: dict[str, dict | None] = {"T1": None, "T2": None, "T3": None}
        self._settings = get_settings()

    @property
    def loaded_models(self) -> dict:
        return dict(self._loaded_models)

    def set_active_selection(
        self, tier: str, provider_type: str, provider_id: str, model_id: str | None = None
    ) -> dict:
        """Set the explicit user-selected model target for a specific tier (T1, T2, T3)."""
        if model_id is None:
            # 3-argument call: (provider_type, provider_id, model_id), default tier T3
            model_id = provider_id
            provider_id = provider_type
            provider_type = tier
            tier = "T3"

        if tier not in {"T1", "T2", "T3"}:
            tier = "T3"

        self._active_selections[tier] = {
            "provider_type": provider_type,
            "provider_id": provider_id,
            "model_id": model_id,
            "selected_at": time.time(),
        }
        return dict(self._active_selections[tier])

    def clear_active_selection(self, tier: str | None = None):
        if tier:
            if tier in self._active_selections:
                self._active_selections[tier] = None
        else:
            self._active_selections = {"T1": None, "T2": None, "T3": None}

    def get_active_selection(self) -> dict | None:
        """Backward compatibility: return active generation target (T3)."""
        return dict(self._active_selections["T3"]) if self._active_selections["T3"] else None

    def get_active_selections(self) -> dict[str, dict | None]:
        """Return full mapping of tier-specific active selections."""
        return {k: (dict(v) if v else None) for k, v in self._active_selections.items()}

    async def get_model_for_tier(self, tier: int) -> str | None:
        """Return the first available model for the given tier, loading it if necessary."""
        selected = await self._get_selected_local_model(f"T{tier}")
        if selected:
            return selected

        candidates = MODEL_TIERS.get(tier, {}).get("models", [])
        for model_id in candidates:
            if model_id in self._loaded_models:
                return model_id

        # No implicit tier-based loading. Loading must come from an explicit
        # user selection or the safety-first fallback path.
        return None

    def get_tier_for_model(self, model_id: str) -> int:
        for tier, info in MODEL_TIERS.items():
            if model_id in info["models"]:
                return tier
        return 0

    def get_kv_config(self, tier: int) -> dict:
        """Get KV config based on tier and global TurboQuant settings."""
        # Baseline from static tiers
        base_config = dict(
            MODEL_TIERS.get(tier, {}).get(
                "kv_cache", {"cache_type_k": "q8_0", "cache_type_v": "q8_0"}
            )
        )

        if self._settings.turboquant_enabled:
            bits = self._settings.turboquant_bits
            # Recommendation: asymmetric is safest for general models (q8_0 K, turbo V)
            turbo_type = f"turbo{bits}"

            # Optionally check turboquant_tier setting
            if (
                self._settings.turboquant_tier == "auto"
                or str(tier) == self._settings.turboquant_tier
            ):
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

    async def get_best_available_model(self, target_tier: int = 1) -> str | None:
        """Get selected or safest loaded model respecting the target tier.

        FIX: Never try to load a model above target_tier - prevents overheating
        on consumer hardware by respecting VRAM constraints.
        """
        # First, check if any model in the desired tier or below is already loaded
        for _tier_level in range(1, target_tier + 1):
            for model_id, info in self._loaded_models.items():
                if info["tier"] <= target_tier:
                    return model_id

        # Check explicit selections for tiers we can afford
        for tier_name in ["T1", "T2", "T3"][:target_tier]:
            selected = await self._get_selected_local_model(tier_name)
            if selected:
                tier = self.get_tier_for_model(selected)
                if tier <= target_tier:
                    return selected

        # Try loading from safety cascade (smallest first), but respect target tier
        # SAFE_FALLBACK_CASCADE is already in ascending order (smallest first)
        for model_id in SAFE_FALLBACK_CASCADE:
            tier = self.get_tier_for_model(model_id)
            if tier > target_tier:
                continue  # Skip models above our tier budget

            if model_id in self._loaded_models:
                return model_id

            kv_config = self.get_kv_config(tier)
            success = await self.lm_client.load_model(
                model_id,
                cache_type_k=kv_config.get("cache_type_k"),
                cache_type_v=kv_config.get("cache_type_v"),
            )
            if success:
                self._loaded_models[model_id] = {
                    "tier": tier,
                    "loaded_at": time.time(),
                    "last_used": time.time(),
                }
                return model_id
        return None

    async def _get_selected_local_model(self, tier: str = "T3") -> str | None:
        """Return/load the explicitly selected local model for a specific tier when supported."""
        selection = self._active_selections.get(tier)
        if not selection or selection.get("provider_type") != "local":
            return None

        provider_id = selection.get("provider_id")
        model_id = selection.get("model_id")
        if not model_id:
            return None

        # The current LM client can execute OpenAI-compatible local runtimes.
        if provider_id not in {"lm_studio", "llama_cpp", "vlm", "ollama"}:
            return None

        if provider_id != "lm_studio":
            return model_id

        if model_id in self._loaded_models:
            return model_id

        tier_num = self.get_tier_for_model(model_id) or int(tier[1])
        kv_config = self.get_kv_config(tier_num)
        success = await self.lm_client.load_model(
            model_id,
            cache_type_k=kv_config.get("cache_type_k"),
            cache_type_v=kv_config.get("cache_type_v"),
        )
        if success:
            self._loaded_models[model_id] = {
                "tier": tier_num,
                "loaded_at": time.time(),
                "last_used": time.time(),
            }
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
                ttl = settings.t2_ttl if hasattr(settings, "t2_ttl") else 600
            elif tier == 3:
                ttl = settings.t3_ttl if hasattr(settings, "t3_ttl") else 300

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
                kv_config["cache_type_v"] = "q4_0"  # Downgrade V cache
                if self._settings.turboquant_enabled:
                    kv_config["cache_type_v"] = "turbo2"  # Max compression
                await self.lm_client.load_model(
                    mid,
                    cache_type_k=kv_config.get("cache_type_k"),
                    cache_type_v=kv_config.get("cache_type_v"),
                )
                self._loaded_models[mid]["last_used"] = time.time()

        elif pressure_level == "orange":
            # Unload T3 models, route to T2
            to_remove = [mid for mid, info in self._loaded_models.items() if info["tier"] == 3]
            for mid in to_remove:
                await self.lm_client.unload_model(mid)
                del self._loaded_models[mid]
                logger.info(f"ORANGE pressure: unloaded T3 model {mid}")
        elif pressure_level == "red":
            # Emergency: unload T2, T1-only with 2K truncation
            to_remove = [mid for mid, info in self._loaded_models.items() if info["tier"] in (2, 3)]
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
                result.append(
                    {
                        "id": model_id,
                        "name": model_id,
                        "tier": tier,
                        "status": "loaded" if is_loaded else "unloaded",
                        "vram_used_mb": loaded_info.get("vram_mb", 0),
                        "kv_cache_config": info["kv_cache"],
                        "max_concurrent": info["max_concurrent"],
                    }
                )
        return result
