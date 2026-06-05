"""System routes: health, config, models, VRAM, cache, metrics."""

import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings
from app import state
from app.services.model_manager import MODEL_TIERS
from app.services.security import is_safe_base_url
from app.services.secrets import (
    get_secret as secrets_get,
    set_secret as secrets_set,
    is_keyring_available as secrets_available,
    warn_fallback_once as secrets_warn_fallback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["system"])
settings = get_settings()

METRICS_DIR = Path("data/metrics")
METRICS_DIR.mkdir(parents=True, exist_ok=True)
_metrics_history: list = []

# Simple KV cache state registry — tracks per-model cache info
_cache_state: dict = {}  # model_id -> {cache_type_k, cache_type_v, context_tokens, estimated_size_mb}

_rotation_history: list = []
_ROTATION_HISTORY_MAX = 50

# Fields that are safe to mutate at runtime via the config PUT endpoint.
# All other fields (e.g. ``ws_auth_token``, ``llm_host``) are locked down
# to prevent abuse and SSRF.
CONFIG_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "llm_model",
    "embedding_model",
    "turboquant_enabled",
    "turboquant_bits",
    "turboquant_residual_window",
    "turboquant_tier",
    "vram_safety_margin_pct",
    "pageindex_model",
    "t2_ttl",
    "t3_ttl",
    "metrics_interval",
})

# Fields that must point at an HTTP(S) URL — guarded by ``is_safe_base_url``
# before any process-wide change is made.
URL_FIELDS: frozenset[str] = frozenset({"llm_host", "embedding_host"})


# ── Pydantic Schemas ──


class SystemConfigUpdate(BaseModel):
    """Request body for PUT /api/v1/config.

    Only the runtime-tunable fields are exposed. Network endpoints
    (``llm_host``, ``embedding_host``), auth tokens, and ports must be
    configured via environment variables so that they cannot be redirected
    by an authenticated caller.
    """
    llm_model: str | None = None
    embedding_model: str | None = None
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_residual_window: int | None = None
    turboquant_tier: str | None = None
    vram_safety_margin_pct: int | None = None
    pageindex_model: str | None = None
    t2_ttl: int | None = None
    t3_ttl: int | None = None
    metrics_interval: float | None = None


class CacheConfigUpdate(BaseModel):
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_tier: str | None = None
    turboquant_residual_window: int | None = None


class ModelSelectionRequest(BaseModel):
    provider_type: str
    provider_id: str
    model_id: str
    tier: Optional[str] = "T3"
    load: bool = False


class KeyRotationRequest(BaseModel):
    key_name: str
    new_value: str


# ── Health ──


@router.get("/health")
async def health_check(response: Response):
    from app.state import vram_monitor, lm_client

    # Check LM Studio
    lm_available = await lm_client.check_health()

    # Check GPU / VRAM
    vram_data = await vram_monitor.poll_once()
    gpu_available = vram_data.get("gpu_available", False)

    # Calculate uptime from module-level startup time
    try:
        from app.state import _startup_time
        uptime = time.time() - _startup_time
    except Exception:
        uptime = 0

    healthy = lm_available and gpu_available
    # Return 503 Service Unavailable when degraded so load balancers and
    # orchestrators correctly remove the instance from rotation. The body
    # still describes the failure for human readers.
    if not healthy:
        response.status_code = 503

    return {
        "status": "ok" if healthy else "degraded",
        "lm_studio": lm_available,
        "gpu": gpu_available,
        "turboquant_tier": settings.turboquant_tier,
        "turboquant_enabled": settings.turboquant_enabled,
        "uptime_seconds": round(uptime, 1),
        "vram_used_pct": vram_data.get("vram_used_pct", 0),
        "active_models_count": len(_cache_state),
        "message": _health_message(lm_available, gpu_available),
    }


def _health_message(lm: bool, gpu: bool) -> str:
    if lm and gpu:
        return "All systems operational."
    if lm:
        return "LM Studio connected but GPU unavailable."
    if gpu:
        return "GPU available but LM Studio not reachable."
    return "Backend running — connect LM Studio and GPU for full functionality."


# ── Readiness ──


@router.get("/ready")
async def readiness_check(response: Response):
    import shutil

    response.headers["Cache-Control"] = "no-cache"

    lm_ok = await state.lm_client.check_health()
    models_loaded = bool(state.model_manager._loaded_models)

    disk = shutil.disk_usage("/")
    disk_free_pct = (disk.free / disk.total) * 100
    disk_ok = disk_free_pct > 10

    checks = {
        "lm_studio": {"ok": lm_ok, "detail": "connected" if lm_ok else "unreachable"},
        "models_loaded": {"ok": models_loaded, "detail": f"{len(state.model_manager._loaded_models)} loaded"},
        "disk_space": {"ok": disk_ok, "detail": f"{disk_free_pct:.1f}% free"},
    }

    ready = lm_ok and models_loaded and disk_ok
    response.status_code = 200 if ready else 503

    return {"status": "ready" if ready else "not_ready", "checks": checks}


@router.get("/system/health/ready")
async def system_health_ready(response: Response):
    import shutil

    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Deployment-Color"] = os.environ.get("DEPLOYMENT_COLOR", "unknown")

    checks = {}

    try:
        lm_ok = await state.lm_client.check_health()
        checks["lm_studio"] = {"ok": lm_ok, "detail": "connected" if lm_ok else "unreachable"}
    except Exception as e:
        checks["lm_studio"] = {"ok": False, "detail": f"error: {str(e)}"}

    try:
        keyring_ok = secrets_available()
        checks["keyring"] = {"ok": keyring_ok, "detail": "available" if keyring_ok else "unavailable"}
    except Exception as e:
        checks["keyring"] = {"ok": False, "detail": f"error: {str(e)}"}

    try:
        disk = shutil.disk_usage("/")
        disk_free_pct = (disk.free / disk.total) * 100
        disk_ok = disk_free_pct > 10
        checks["disk_space"] = {"ok": disk_ok, "detail": f"{disk_free_pct:.1f}% free"}
    except Exception as e:
        checks["disk_space"] = {"ok": False, "detail": f"error: {str(e)}"}

    try:
        data_dir = Path("data")
        data_ok = data_dir.exists() and os.access(str(data_dir), os.W_OK)
        checks["data_volume"] = {"ok": data_ok, "detail": "writable" if data_ok else "not writable"}
    except Exception as e:
        checks["data_volume"] = {"ok": False, "detail": f"error: {str(e)}"}

    try:
        db_path = Path("data/user")
        db_ok = db_path.exists()
        checks["database"] = {"ok": db_ok, "detail": "exists" if db_ok else "missing"}
    except Exception as e:
        checks["database"] = {"ok": False, "detail": f"error: {str(e)}"}

    all_ok = all(c["ok"] for c in checks.values())
    response.status_code = 200 if all_ok else 503

    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
        "deployment_color": os.environ.get("DEPLOYMENT_COLOR", "unknown"),
    }


# ── Config ──


@router.get("/config")
async def get_config():
    return {
        "llm_host": settings.llm_host,
        "llm_port": settings.llm_port,
        "llm_model": settings.llm_model,
        "embedding_host": settings.embedding_host,
        "embedding_model": settings.embedding_model,
        "turboquant_enabled": settings.turboquant_enabled,
        "turboquant_bits": settings.turboquant_bits,
        "turboquant_tier": settings.turboquant_tier,
        "turboquant_residual_window": settings.turboquant_residual_window,
        "vram_safety_margin_pct": settings.vram_safety_margin_pct,
        "backend_port": settings.backend_port,
        "frontend_port": settings.frontend_port,
        "search_provider": os.environ.get("SEARCH_PROVIDER", "perplexity"),
        "pageindex_model": settings.pageindex_model,
        "t2_ttl": settings.t2_ttl,
        "t3_ttl": settings.t3_ttl,
    }


@router.put("/config")
async def update_config(request: Request):
    """Update runtime configuration. Only safe, whitelisted fields are mutable.

    Sensitive fields like ``ws_auth_token``, ``llm_host``, and ``llm_api_key``
    are intentionally excluded from the whitelist to prevent abuse and SSRF.
    To change them, restart the process with new environment variables.

    We read the raw request body (instead of a Pydantic model) so that
    *any* unknown field — even one a future contributor forgets to exclude
    from the model — is reported back to the caller as ``rejected_fields``
    and never reaches ``settings``.
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "InvalidJSON", "message": "Request body must be valid JSON object."},
        )

    if not isinstance(data, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "InvalidPayload", "message": "Expected a JSON object."},
        )

    updates = []
    rejected = []

    for key, value in data.items():
        # Reject any field outside the explicit whitelist. This prevents
        # the caller from setting ``ws_auth_token``, ``llm_host``, or any
        # other sensitive attribute that would let them redirect traffic.
        if key not in CONFIG_ALLOWED_FIELDS:
            rejected.append(key)
            continue
        if not hasattr(settings, key):
            rejected.append(key)
            continue
        setattr(settings, key, value)
        updates.append(key)
        env_key = key.upper()
        os.environ[env_key] = str(value)

    if rejected:
        logger.warning(
            "config_update: rejected non-whitelisted fields: %s", rejected
        )
        from app.services.audit import audit
        audit("config.update_rejected", fields=rejected)

    if updates:
        from app.services.audit import audit
        audit("config.updated", fields=updates)

    # Clear the lru cache on get_settings so future calls return updated settings
    get_settings.cache_clear()

    return {
        "updated": len(updates) > 0,
        "fields_updated": updates,
        "rejected_fields": rejected,
        **{k: getattr(settings, k, None) for k in updates},
    }


# ── Key Rotation ──


def _mask_value(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.post("/secrets/rotate")
async def rotate_key(payload: KeyRotationRequest):
    key_name = payload.key_name.strip()
    new_value = payload.new_value

    if not key_name:
        return JSONResponse(
            status_code=400,
            content={"error": "InvalidKey", "message": "key_name must not be empty."},
        )

    old_value = secrets_get(key_name)

    try:
        secrets_set(key_name, new_value)
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "KeyringWriteFailed", "message": str(exc)},
        )

    os.environ[key_name] = new_value

    rotation_event = {
        "key_name": key_name,
        "old_value_masked": _mask_value(old_value) if old_value else "(empty)",
        "new_value_masked": _mask_value(new_value),
        "rotated_at": time.time(),
    }
    _rotation_history.append(rotation_event)
    if len(_rotation_history) > _ROTATION_HISTORY_MAX:
        _rotation_history.pop(0)

    from app.services.audit import audit
    audit("secret.rotated", key_name=key_name)

    logger.info("key_rotation: rotated %s", key_name)

    return {
        "success": True,
        "key_name": key_name,
        "old_value_masked": rotation_event["old_value_masked"],
        "new_value_masked": rotation_event["new_value_masked"],
        "rotated_at": rotation_event["rotated_at"],
    }


@router.get("/secrets/rotation-history")
async def get_rotation_history():
    return {"history": _rotation_history, "count": len(_rotation_history)}


# ── Models ──


@router.get("/models")
async def list_models():
    from app.state import lm_client, model_manager

    # Get models from LM Studio
    lm_models = await lm_client.list_models()
    lm_model_ids = {m.get("id", m.get("name", "")) for m in lm_models}

    # Build response enriched with manager data
    loaded = model_manager._loaded_models
    tier_info = {}

    for tier_num, tier_data in MODEL_TIERS.items():
        for mid in tier_data.get("models", []):
            tier_info[mid] = tier_data

    result = []

    # All known models (from LM Studio + manager)
    all_ids = lm_model_ids | set(loaded.keys())

    for mid in sorted(all_ids):
        tier = model_manager.get_tier_for_model(mid) or 0
        is_loaded = mid in loaded
        loaded_info = loaded.get(mid, {})
        kv = tier_info.get(mid, {}).get("kv_cache", {})

        result.append({
            "id": mid,
            "name": mid,
            "tier": tier,
            "status": "loaded" if is_loaded else "available",
            "vram_used_mb": loaded_info.get("vram_mb", 0),
            "loaded_at": loaded_info.get("loaded_at"),
            "last_used": loaded_info.get("last_used"),
            "turboquant_config": kv,
        })

    # If no models found, return tier defaults as available
    if not result:
        result = model_manager.get_status()

    return result


@router.get("/models/discover")
async def discover_models():
    """Discover local and configured cloud models without exposing secrets."""
    return await state.model_discovery.discover(
        active_selection=state.model_manager.get_active_selection(),
        active_selections=state.model_manager.get_active_selections(),
    )


@router.get("/models/selection")
async def get_model_selection():
    return {
        "active_selection": state.model_manager.get_active_selection(),
        "active_selections": state.model_manager.get_active_selections(),
    }


@router.post("/models/select")
async def select_model(payload: ModelSelectionRequest):
    """Select the model target explicitly before inference/loading."""
    tier = payload.tier or "T3"
    selection = state.model_manager.set_active_selection(
        tier,
        payload.provider_type,
        payload.provider_id,
        payload.model_id,
    )

    execution = _configure_selected_provider(payload.provider_type, payload.provider_id)
    loaded = False
    if payload.load and payload.provider_type == "local" and payload.provider_id == "lm_studio":
        loaded = (await state.model_manager.get_best_available_model()) == payload.model_id

    return {
        "selected": True,
        "active_selection": selection,
        "active_selections": state.model_manager.get_active_selections(),
        "generation_supported": execution["generation_supported"],
        "load_requested": payload.load,
        "loaded": loaded,
        "message": execution["message"],
    }


def _configure_selected_provider(provider_type: str, provider_id: str) -> dict:
    """Configure OpenAI-compatible generation endpoints for selected providers."""
    settings = get_settings()
    local_base_urls = {
        "lm_studio": settings.llm_host,
        "ollama": os.environ.get("OLLAMA_OPENAI_HOST") or os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "llama_cpp": os.environ.get("LLAMA_CPP_HOST", ""),
        "vlm": os.environ.get("VLM_HOST", ""),
    }
    cloud_configs = {
        "openai": ("https://api.openai.com", secrets_get("OPENAI_API_KEY")),
        "mistral": ("https://api.mistral.ai", secrets_get("MISTRAL_API_KEY")),
        "openrouter": ("https://api.openrouter.ai/api", secrets_get("OPENROUTER_API_KEY")),
        "opencode": (os.environ.get("OPENCODE_BASE_URL", ""), secrets_get("OPENCODE_API_KEY")),
    }

    if provider_type == "local" and provider_id in local_base_urls and local_base_urls[provider_id]:
        state.lm_client.configure_endpoint(local_base_urls[provider_id], settings.llm_api_key)
        return {
            "generation_supported": True,
            "message": f"Selected {provider_id}; OpenAI-compatible endpoint configured.",
        }

    if provider_type == "cloud" and provider_id in cloud_configs:
        base_url, api_key = cloud_configs[provider_id]
        if base_url and api_key:
            state.lm_client.configure_endpoint(base_url, api_key)
            return {
                "generation_supported": True,
                "message": f"Selected {provider_id}; cloud OpenAI-compatible endpoint configured.",
            }
        return {
            "generation_supported": False,
            "message": f"{provider_id} is missing API key or base URL.",
        }

    return {
        "generation_supported": False,
        "message": f"{provider_id} was selected for discovery, but generation routing is not implemented yet.",
    }


@router.post("/models/{model_id}/load")
async def load_model(model_id: str):
    from app.state import lm_client, model_manager

    try:
        success = await lm_client.load_model(model_id)
    except Exception as e:
        logger.error(f"Model load failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "model_id": model_id,
                "status": "failed",
                "error": "ModelLoadFailed",
                "message": str(e),
            },
        )

    if success:
        tier = model_manager.get_tier_for_model(model_id) or 1
        model_manager._loaded_models[model_id] = {
            "tier": tier,
            "loaded_at": time.time(),
            "last_used": time.time(),
        }
        from app.services.audit import audit
        audit("model.loaded", model_id=model_id, tier=tier)

    return {
        "model_id": model_id,
        "status": "loaded" if success else "failed",
        "tier": model_manager.get_tier_for_model(model_id),
    }


@router.post("/models/{model_id}/unload")
async def unload_model(model_id: str):
    from app.state import lm_client, model_manager

    success = await lm_client.unload_model(model_id)

    if success and model_id in model_manager._loaded_models:
        del model_manager._loaded_models[model_id]
        from app.services.audit import audit
        audit("model.unloaded", model_id=model_id)

    return {
        "model_id": model_id,
        "status": "unloaded" if success else "failed",
    }


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
    from app.state import model_manager

    s = settings
    models_info = {}

    for model_id, info in model_manager._loaded_models.items():
        tier = info.get("tier", 1)
        kv = model_manager.get_kv_config(tier)
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
async def evict_cache(payload: Optional[dict] = None):
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


# ── Maintenance ──


@router.post("/maintenance/sessions/cleanup")
async def cleanup_sessions():
    """Run a one-shot sweep of old session artifacts.

    Removes files under ``data/user/{solve,research,notebooks,guide}``
    whose mtime is older than ``UDIP_SESSION_MAX_AGE_DAYS`` (default 30).
    Returns a small report with counts and any per-file errors so the
    operator can see what happened. Safe to call repeatedly; the walk
    is idempotent.
    """
    from app.services.session_cleanup import run_cleanup
    return run_cleanup().to_dict()


@router.post("/metrics/benchmarks/run")
async def run_benchmarks(payload: Optional[dict] = None):
    from app.state import benchmark_runner
    category = "all"
    if payload and "category" in payload:
        category = payload["category"]
    if category not in ("all", "latency", "kv_cache", "quality", "throughput"):
        return {"error": f"Unknown category: {category}. Valid: all, latency, kv_cache, quality, throughput"}
    run_id = await benchmark_runner.start_run(category)
    return {"run_id": run_id, "category": category, "status": "queued"}


@router.get("/metrics/benchmarks/{run_id}")
async def get_benchmark_status(run_id: str):
    from app.state import benchmark_runner
    run = benchmark_runner.get_run(run_id)
    if run is None:
        return {"run_id": run_id, "status": "not_found"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/metrics/benchmarks/latest")
async def get_latest_benchmark():
    from app.state import benchmark_runner
    run = benchmark_runner.get_latest_run()
    if run is None:
        return {"status": "no_runs"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


# ── Provider Marketplace Config & Health ──

from app.services.model_discovery import LOCAL_PROVIDERS, CLOUD_PROVIDERS

class ProviderConfigRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class ProviderHealthRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None


def _update_env_file(updates: dict[str, str]):
    from pathlib import Path
    env_path = Path(".env")
    lines = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            pass
            
    env_vars = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                env_vars[parts[0].strip()] = parts[1].strip()
            
    for k, v in updates.items():
        env_vars[k] = v
        
    new_lines = []
    seen = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                k_strip = parts[0].strip()
                if k_strip in updates:
                    new_lines.append(f"{k_strip}={updates[k_strip]}")
                    seen.add(k_strip)
                    continue
        new_lines.append(line)
        
    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")
            
    try:
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to write to .env file: {e}")


@router.post("/models/providers/{provider_id}/config")
async def configure_provider(provider_id: str, payload: ProviderConfigRequest):
    """Save provider settings and reload settings immediately.

    API keys are stored in the OS keyring (Windows Credential Manager /
    macOS Keychain / libsecret) and never written to ``.env``. The
    base URL is not secret and continues to be persisted to ``.env``
    for restart durability.

    If no keyring backend is available the endpoint returns HTTP 503
    with a clear remediation message — we will not silently fall back
    to plaintext on disk.
    """
    spec = next((p for p in LOCAL_PROVIDERS + CLOUD_PROVIDERS if p.id == provider_id), None)
    if not spec:
        return {"success": False, "error": f"Unknown provider: {provider_id}"}

    # Identify env keys
    key_env = None
    if spec.api_key_env:
        key_env = spec.api_key_env if isinstance(spec.api_key_env, str) else spec.api_key_env[0]

    url_env = spec.base_url_env

    # Sanitize inputs to prevent CRLF injection in .env files
    import re
    def sanitize(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return re.sub(r"[\r\n]", "", v).strip()

    api_key_clean = sanitize(payload.api_key)
    base_url_clean = sanitize(payload.base_url)

    env_updates: dict[str, str] = {}     # -> .env + os.environ
    secret_updates: dict[str, str] = {}   # -> keyring only

    # Special cases
    if provider_id == "lm_studio":
        if base_url_clean:
            # SSRF guard: refuse URLs pointing at internal networks, AWS
            # metadata endpoints, or other unsafe hosts. Loopback and
            # private ranges require ``UDIP_ALLOW_LOCAL_LLM=1``.
            if not is_safe_base_url(base_url_clean):
                raise HTTPException(
                    status_code=400,
                    detail="base_url is not allowed (SSRF protection)",
                )
            env_updates["LLM_HOST"] = base_url_clean
        if api_key_clean:
            secret_updates["LLM_API_KEY"] = api_key_clean
    else:
        if api_key_clean and key_env:
            secret_updates[key_env] = api_key_clean
        if base_url_clean and url_env:
            if not is_safe_base_url(base_url_clean):
                raise HTTPException(
                    status_code=400,
                    detail="base_url is not allowed (SSRF protection)",
                )
            env_updates[url_env] = base_url_clean

    if not env_updates and not secret_updates:
        return {"success": False, "error": "No configuration parameters provided to update"}

    # Persist secrets in the OS keyring. Refuse the write rather than
    # silently fall back to plaintext on disk.
    if secret_updates and not secrets_available():
        secrets_warn_fallback("no functional backend detected")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": "KeyringUnavailable",
                "message": (
                    "OS keyring is not available, refusing to write the API "
                    "key in plaintext. Install a keyring backend "
                    "(Windows Credential Manager / macOS Keychain / libsecret "
                    "on Linux) or set the key via environment variable."
                ),
                "env_var": next(iter(secret_updates)),
            },
        )

    for env_name, value in secret_updates.items():
        try:
            secrets_set(env_name, value)
        except RuntimeError as exc:
            return JSONResponse(
                status_code=503,
                content={"success": False, "error": "KeyringWriteFailed", "message": str(exc)},
            )
        # Mirror into the current process so the running server can use it
        # without a restart, but DO NOT mirror to .env.
        os.environ[env_name] = value

    # Persist non-secret settings (base URLs, etc.) to .env as before.
    if env_updates:
        _update_env_file(env_updates)
        for k, v in env_updates.items():
            os.environ[k] = v

    # Clear settings cache so get_settings() reloads from modified .env
    get_settings.cache_clear()

    # Also update settings fields directly in-memory for current settings singleton
    global settings
    import app.routers.system
    app.routers.system.settings = get_settings()

    for key, val in env_updates.items():
        attr_name = key.lower()
        if hasattr(app.routers.system.settings, attr_name):
            setattr(app.routers.system.settings, attr_name, val)

    # Reconfigure the active provider if the configured provider is selected
    from app import state
    active_selection = state.model_manager.get_active_selection()
    if active_selection and active_selection.get("provider_id") == provider_id:
        _configure_selected_provider(active_selection["provider_type"], provider_id)

    return {
        "success": True,
        "message": f"Successfully updated configuration for {spec.name}.",
        "updated_keys": list(env_updates.keys()) + list(secret_updates.keys()),
        "stored_in": "keyring" if secret_updates else "env",
    }


@router.post("/models/providers/{provider_id}/health")
async def check_provider_health(provider_id: str, payload: Optional[ProviderHealthRequest] = None):
    """Test on-demand connection health and latency for a given provider, with optional override parameters."""
    api_key = payload.api_key if payload else None
    base_url = payload.base_url if payload else None
    
    from app import state
    health_result = await state.model_discovery.test_health(
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url
    )
    return health_result


# ── GDPR Data Management ─────────────────────────────────────────────

USER_DATA_DIRS = ["solve", "research", "notebooks", "guide"]


@router.get("/system/data/export")
async def export_user_data():
    """Export all user data as a ZIP archive (GDPR data portability)."""
    import io
    import zipfile
    import json as _json

    data_root = Path("data/user")
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for subdir in USER_DATA_DIRS:
            dir_path = data_root / subdir
            if not dir_path.exists():
                continue
            for f in dir_path.rglob("*"):
                if f.is_file():
                    arcname = f"data/{subdir}/{f.relative_to(dir_path)}"
                    zf.write(f, arcname)
                    file_count += 1

        metadata = {
            "exported_at": time.time(),
            "file_count": file_count,
            "directories": USER_DATA_DIRS,
        }
        zf.writestr("metadata.json", _json.dumps(metadata, indent=2))

    buf.seek(0)
    ts = int(time.time())
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=udip-export-{ts}.zip"},
    )


@router.delete("/system/data")
async def delete_user_data(confirm: bool = False):
    """Delete all user data (GDPR right to erasure). Requires confirm=true."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to delete all user data")

    data_root = Path("data/user")
    deleted = 0

    for subdir in USER_DATA_DIRS:
        dir_path = data_root / subdir
        if not dir_path.exists():
            continue
        for f in dir_path.rglob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning("Failed to delete %s: %s", f, e)

    logger.info("GDPR deletion: removed %d files", deleted)
    return {"deleted_count": deleted}


@router.get("/system/data/summary")
async def data_summary():
    """Summary of stored user data (file counts and sizes per directory)."""
    data_root = Path("data/user")
    directories = {}
    total_files = 0
    total_size = 0

    for subdir in USER_DATA_DIRS:
        dir_path = data_root / subdir
        if not dir_path.exists():
            directories[subdir] = {"files": 0, "size_bytes": 0}
            continue
        count = 0
        size = 0
        for f in dir_path.rglob("*"):
            if f.is_file():
                count += 1
                size += f.stat().st_size
        directories[subdir] = {"files": count, "size_bytes": size}
        total_files += count
        total_size += size

    return {
        "directories": directories,
        "total_files": total_files,
        "total_size_bytes": total_size,
    }


# ── Backup endpoints ────────────────────────────────────────────────


@router.post("/backup")
async def create_backup(kb_name: Optional[str] = None):
    """Create a backup of knowledge bases.

    If ``kb_name`` is provided, only that KB is backed up.
    Otherwise, all knowledge bases are backed up.
    """
    from app.services.backup import create_backup as _create_backup
    from app.services.audit import audit

    result = _create_backup(kb_name)
    if result["success"]:
        audit("backup.created", kb_name=kb_name, backup_name=result["name"])
        return result
    raise HTTPException(status_code=500, detail=result["error"])


@router.get("/backup")
async def list_backups():
    """List all available knowledge base backups."""
    from app.services.backup import list_backups as _list_backups
    return {"backups": _list_backups()}


@router.post("/backup/{backup_name}/restore")
async def restore_backup(backup_name: str, kb_name: Optional[str] = None):
    """Restore a knowledge base from backup."""
    from app.services.backup import restore_backup as _restore_backup
    from app.services.audit import audit
    from app.services.security import safe_name

    safe_backup = safe_name(backup_name)
    if not safe_backup or safe_backup == "default":
        raise HTTPException(status_code=400, detail="Invalid backup name")

    result = _restore_backup(safe_backup, kb_name)
    if result["success"]:
        audit("backup.restored", backup_name=result["name"], kb_name=kb_name)
        return result
    raise HTTPException(status_code=404, detail=result["error"])
