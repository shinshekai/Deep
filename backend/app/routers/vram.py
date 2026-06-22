"""VRAM, cache, and metrics routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import state
from app.config import get_settings
from app.routers.system_shared import _cache_state, _metrics_history

router = APIRouter(prefix="/api/v1", tags=["system"])
settings = get_settings()


class CacheConfigUpdate(BaseModel):
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_tier: str | None = None
    turboquant_residual_window: int | None = None


# ── VRAM ──


@router.get("/vram/status")
async def get_vram_status():
    from app.state import vram_monitor

    data = await vram_monitor.poll_once()

    total = data.get("vram_total_mb", 0)
    used = data.get("vram_used_mb", 0)
    free = max(0, total - used)

    # Build a basic breakdown showing tier-level estimates
    breakdown = {}
    if data.get("gpu_available"):
        breakdown = {
            "total_gpu_memory_mb": round(total, 1),
            "used_gpu_memory_mb": round(used, 1),
            "free_gpu_memory_mb": round(free, 1),
            "gpu_utilization_pct": round(data.get("vram_used_pct", 0), 1),
        }

    return {
        "total_mb": round(total, 1),
        "used_mb": round(used, 1),
        "free_mb": round(free, 1),
        "utilization_pct": round(data.get("vram_used_pct", 0), 1),
        "pressure_level": data.get("pressure_level", "green"),
        "gpu_available": data.get("gpu_available", False),
        "breakdown": breakdown,
    }


# ── Cache ──


@router.get("/cache/status")
async def cache_status():
    s = settings
    models_info = {}

    for model_id, info in state.model_manager._loaded_models.items():
        tier = info.get("tier", 1)
        kv = state.model_manager.get_kv_config(tier)
        cache_entry = _cache_state.get(model_id, {})

        models_info[model_id] = {
            "tier": tier,
            "cache_type_k": kv.get("cache_type_k", "f16"),
            "cache_type_v": kv.get("cache_type_v", "f16"),
            "context_tokens": cache_entry.get("context_tokens", 0),
            "estimated_size_mb": cache_entry.get("estimated_size_mb", 0),
        }

    return {
        "turboquant_enabled": s.turboquant_enabled,
        "turboquant_bits": s.turboquant_bits,
        "turboquant_tier": s.turboquant_tier,
        "turboquant_residual_window": s.turboquant_residual_window,
        "models": models_info,
        "tracked_entries": len(_cache_state),
    }


@router.put("/cache/config")
async def update_cache_config(payload: CacheConfigUpdate):
    data = payload.model_dump(exclude_unset=True)

    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    return {
        "updated": True,
        "config": {
            "turboquant_enabled": settings.turboquant_enabled,
            "turboquant_bits": settings.turboquant_bits,
            "turboquant_tier": settings.turboquant_tier,
            "turboquant_residual_window": settings.turboquant_residual_window,
        },
    }


@router.post("/cache/evict")
async def evict_cache(payload: dict | None = None):
    model_id = payload.get("model_id") if payload else None

    if model_id and model_id in _cache_state:
        freed = _cache_state[model_id].get("estimated_size_mb", 0)
        del _cache_state[model_id]
        return {"evicted": True, "model_id": model_id, "freed_mb": freed}

    # Evict all non-pinned cache entries
    count = len(_cache_state)
    _cache_state.clear()
    return {"evicted": True, "entries_cleared": count}


# ── Metrics ──


@router.get("/metrics/history")
async def get_metrics_history():
    return _metrics_history
