"""Model management, selection, and provider configuration routes."""

import contextlib
import logging
import os
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import state
from app.config import get_settings
from app.services.model_discovery import CLOUD_PROVIDERS, LOCAL_PROVIDERS
from app.services.model_manager import MODEL_TIERS
from app.services.secrets import get_secret as secrets_get
from app.services.secrets import is_keyring_available as secrets_available
from app.services.secrets import set_secret as secrets_set
from app.services.secrets import warn_fallback_once as secrets_warn_fallback
from app.services.security import is_safe_base_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["models"])
settings = get_settings()


# -- Pydantic Schemas --


class CacheConfigUpdate(BaseModel):
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_tier: str | None = None
    turboquant_residual_window: int | None = None


class ModelSelectionRequest(BaseModel):
    provider_type: str
    provider_id: str
    model_id: str
    tier: str | None = "T3"
    load: bool = False


class ProviderConfigRequest(BaseModel):
    api_key: str | None = None
    base_url: str | None = None


class ProviderHealthRequest(BaseModel):
    api_key: str | None = None
    base_url: str | None = None


# -- Models --


@router.get("/models")
async def list_models():
    from app.state import lm_client, model_manager

    # Get models from LM Studio
    lm_models = await lm_client.list_models()
    lm_model_ids = {m.get("id", m.get("name", "")) for m in lm_models}

    # Build response enriched with manager data
    loaded = model_manager._loaded_models
    tier_info = {}

    for _tier_num, tier_data in MODEL_TIERS.items():
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

        result.append(
            {
                "id": mid,
                "name": mid,
                "tier": tier,
                "status": "loaded" if is_loaded else "available",
                "vram_used_mb": loaded_info.get("vram_mb", 0),
                "loaded_at": loaded_info.get("loaded_at"),
                "last_used": loaded_info.get("last_used"),
                "turboquant_config": kv,
            }
        )

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
        "ollama": os.environ.get("OLLAMA_OPENAI_HOST")
        or os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
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


# -- Provider Marketplace Config & Health --


def _update_env_file(updates: dict[str, str]):
    from pathlib import Path

    env_path = Path(".env")
    lines = []
    if env_path.exists():
        with contextlib.suppress(Exception):
            lines = env_path.read_text(encoding="utf-8").splitlines()

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

    def sanitize(v: str | None) -> str | None:
        if v is None:
            return None
        return re.sub(r"[\r\n]", "", v).strip()

    api_key_clean = sanitize(payload.api_key)
    base_url_clean = sanitize(payload.base_url)

    env_updates: dict[str, str] = {}  # -> .env + os.environ
    secret_updates: dict[str, str] = {}  # -> keyring only

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
    settings = get_settings()

    for key, val in env_updates.items():
        attr_name = key.lower()
        if hasattr(settings, attr_name):
            setattr(settings, attr_name, val)

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
async def check_provider_health(provider_id: str, payload: ProviderHealthRequest | None = None):
    """Test on-demand connection health and latency for a given provider, with optional override parameters."""
    api_key = payload.api_key if payload else None
    base_url = payload.base_url if payload else None

    from app import state

    health_result = await state.model_discovery.test_health(
        provider_id=provider_id, api_key=api_key, base_url=base_url
    )
    return health_result
