"""Health and readiness check routes."""

import os
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Response

from app import state
from app.config import get_settings
from app.routers.system_shared import _cache_state
from app.services.secrets import is_keyring_available as secrets_available

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check(response: Response):
    from app.state import lm_client, vram_monitor

    lm_available = await lm_client.check_health()
    vram_data = await vram_monitor.poll_once()
    gpu_available = vram_data.get("gpu_available", False)

    try:
        from app.state import _startup_time

        uptime = time.time() - _startup_time
    except Exception:
        uptime = 0

    healthy = lm_available and gpu_available
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


@router.get("/ready")
async def readiness_check(response: Response):
    response.headers["Cache-Control"] = "no-cache"

    lm_ok = await state.lm_client.check_health()
    models_loaded = bool(state.model_manager._loaded_models)

    disk = shutil.disk_usage("/")
    disk_free_pct = (disk.free / disk.total) * 100
    disk_ok = disk_free_pct > 10

    checks = {
        "lm_studio": {"ok": lm_ok, "detail": "connected" if lm_ok else "unreachable"},
        "models_loaded": {
            "ok": models_loaded,
            "detail": f"{len(state.model_manager._loaded_models)} loaded",
        },
        "disk_space": {"ok": disk_ok, "detail": f"{disk_free_pct:.1f}% free"},
    }

    ready = lm_ok and models_loaded and disk_ok
    response.status_code = 200 if ready else 503
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@router.get("/system/health/ready")
async def system_health_ready(response: Response):
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Deployment-Color"] = os.environ.get("DEPLOYMENT_COLOR", "unknown")

    checks = {}

    try:
        lm_ok = await state.lm_client.check_health()
        checks["lm_studio"] = {"ok": lm_ok, "detail": "connected" if lm_ok else "unreachable"}
    except Exception as e:
        checks["lm_studio"] = {"ok": False, "detail": f"error: {e!s}"}

    try:
        keyring_ok = secrets_available()
        checks["keyring"] = {"ok": keyring_ok, "detail": "available" if keyring_ok else "unavailable"}
    except Exception as e:
        checks["keyring"] = {"ok": False, "detail": f"error: {e!s}"}

    try:
        disk = shutil.disk_usage("/")
        disk_free_pct = (disk.free / disk.total) * 100
        disk_ok = disk_free_pct > 10
        checks["disk_space"] = {"ok": disk_ok, "detail": f"{disk_free_pct:.1f}% free"}
    except Exception as e:
        checks["disk_space"] = {"ok": False, "detail": f"error: {e!s}"}

    try:
        data_dir = Path("data")
        data_ok = data_dir.exists() and os.access(str(data_dir), os.W_OK)
        checks["data_volume"] = {"ok": data_ok, "detail": "writable" if data_ok else "not writable"}
    except Exception as e:
        checks["data_volume"] = {"ok": False, "detail": f"error: {e!s}"}

    try:
        db_path = Path("data/user")
        db_ok = db_path.exists()
        checks["database"] = {"ok": db_ok, "detail": "exists" if db_ok else "missing"}
    except Exception as e:
        checks["database"] = {"ok": False, "detail": f"error: {e!s}"}

    all_ok = all(c["ok"] for c in checks.values())
    response.status_code = 200 if all_ok else 503

    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
        "deployment_color": os.environ.get("DEPLOYMENT_COLOR", "unknown"),
    }
