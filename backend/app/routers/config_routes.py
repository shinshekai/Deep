"""Runtime configuration and secrets rotation routes."""

import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings
from app.routers.system_shared import CONFIG_ALLOWED_FIELDS, _ROTATION_HISTORY_MAX, _mask_value, _rotation_history, logger
from app.services.secrets import get_secret as secrets_get
from app.services.secrets import is_keyring_available as secrets_available
from app.services.secrets import set_secret as secrets_set
from app.services.secrets import warn_fallback_once as secrets_warn_fallback

router = APIRouter(prefix="/api/v1", tags=["config"])


class KeyRotationRequest(BaseModel):
    key_name: str
    new_value: str


class SystemConfigUpdate(BaseModel):
    """System config update request model. (unused, kept for schema compatibility)"""
    ...


# ── Config ──


@router.get("/config")
async def get_config():
    s = get_settings()
    return {
        "llm_host": s.llm_host,
        "llm_port": s.llm_port,
        "llm_model": s.llm_model,
        "embedding_host": s.embedding_host,
        "embedding_model": s.embedding_model,
        "turboquant_enabled": s.turboquant_enabled,
        "turboquant_bits": s.turboquant_bits,
        "turboquant_tier": s.turboquant_tier,
        "turboquant_residual_window": s.turboquant_residual_window,
        "vram_safety_margin_pct": s.vram_safety_margin_pct,
        "backend_port": s.backend_port,
        "frontend_port": s.frontend_port,
        "search_provider": os.environ.get("SEARCH_PROVIDER", "perplexity"),
        "pageindex_model": s.pageindex_model,
        "t2_ttl": s.t2_ttl,
        "t3_ttl": s.t3_ttl,
        "enable_thinking": s.enable_thinking,
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
        if not hasattr(get_settings(), key):
            rejected.append(key)
            continue
        env_key = key.upper()
        os.environ[env_key] = str(value)
        updates.append(key)

    if rejected:
        logger.warning("config_update: rejected non-whitelisted fields: %s", rejected)
        from app.services.audit import audit

        audit("config.update_rejected", fields=rejected)

    if updates:
        from app.services.audit import audit
        audit("config.updated", fields=updates)

    get_settings.cache_clear()

    s = get_settings()
    return {
        "updated": len(updates) > 0,
        "fields_updated": updates,
        "rejected_fields": rejected,
        **{k: getattr(s, k, None) for k in updates},
    }


# ── Key Rotation ──


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
