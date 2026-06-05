import pytest
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.services import secrets as secrets_mod

client = TestClient(app)

def test_health_endpoint():
    with patch("app.state.lm_client") as mock_lm:
        mock_lm.check_health = AsyncMock(return_value=True)
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={
                "vram_total_mb": 1000,
                "vram_used_mb": 500,
                "vram_used_pct": 50.0,
                "gpu_available": True,
            })
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert "status" in response.json()


def test_health_endpoint_returns_503_when_degraded():
    """Degraded health (no LM Studio, no GPU) must return HTTP 503 so
    load balancers correctly remove the instance from rotation."""
    with patch("app.state.lm_client") as mock_lm:
        mock_lm.check_health = AsyncMock(return_value=False)
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={
                "vram_total_mb": 0,
                "vram_used_mb": 0,
                "vram_used_pct": 0,
                "gpu_available": False,
            })
            response = client.get("/api/v1/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"

def test_config_endpoint():
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    assert "llm_host" in response.json()


def test_discover_models_endpoint(mock_model_discovery):
    mock_model_discovery.discover.return_value = {
        "local": [{"id": "lm_studio", "models": [{"id": "qwen-small"}]}],
        "cloud": [],
        "active_selection": None,
    }

    response = client.get("/api/v1/models/discover")

    assert response.status_code == 200
    assert response.json()["local"][0]["id"] == "lm_studio"


def test_select_model_endpoint_records_explicit_choice(mock_mm, mock_lm):
    response = client.post(
        "/api/v1/models/select",
        json={
            "provider_type": "local",
            "provider_id": "lm_studio",
            "model_id": "qwen-small",
            "load": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["selected"] is True
    mock_mm.set_active_selection.assert_called_with("T3", "local", "lm_studio", "qwen-small")
    mock_lm.configure_endpoint.assert_called()


def test_select_model_endpoint_records_tier(mock_mm, mock_lm):
    response = client.post(
        "/api/v1/models/select",
        json={
            "provider_type": "local",
            "provider_id": "lm_studio",
            "model_id": "nemotron-small",
            "tier": "T2",
            "load": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["selected"] is True
    mock_mm.set_active_selection.assert_called_with("T2", "local", "lm_studio", "nemotron-small")
    mock_lm.configure_endpoint.assert_called()


def test_configure_provider_endpoint():
    response = client.post(
        "/api/v1/models/providers/openai/config",
        json={
            "api_key": "sk-new-test-key",
            "base_url": "https://api.openai.com",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "OPENAI_API_KEY" in response.json()["updated_keys"]


def test_check_provider_health_endpoint():
    with patch("app.state.model_discovery") as mock_md:
        mock_md.test_health = AsyncMock(return_value={
            "status": "available",
            "latency_ms": 42.5,
            "model_count": 3,
            "error": None
        })

        response = client.post(
            "/api/v1/models/providers/openai/health",
            json={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "available"
        assert response.json()["latency_ms"] == 42.5
        assert response.json()["model_count"] == 3


# ── Security headers ─────────────────────────────────────────────────────

def test_security_headers_on_every_response():
    """Every response must include the defense-in-depth security headers."""
    with patch("app.state.lm_client") as mock_lm:
        mock_lm.check_health = AsyncMock(return_value=True)
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={
                "vram_total_mb": 1000, "vram_used_mb": 500,
                "vram_used_pct": 50.0, "gpu_available": True,
            })
            response = client.get("/api/v1/health")

    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"
    # CSP must forbid all framing
    csp = response.headers.get("content-security-policy", "")
    assert "frame-ancestors 'none'" in csp
    # HSTS only sent when UDIP_HSTS_ENABLED=1
    assert "strict-transport-security" not in response.headers


# ── Config PUT whitelist ─────────────────────────────────────────────────

def test_config_put_rejects_sensitive_fields():
    """llm_host, llm_api_key, ws_auth_token must be ignored even if sent."""
    response = client.put(
        "/api/v1/config",
        json={
            "llm_host": "http://169.254.169.254",
            "llm_api_key": "sk-attacker",
            "ws_auth_token": "leaked",
            "llm_model": "Qwen3-1.7B-Q4_K_M",  # safe
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Sensitive fields must show up in rejected_fields, not in fields_updated
    assert "llm_host" in data["rejected_fields"]
    assert "llm_api_key" in data["rejected_fields"]
    assert "ws_auth_token" in data["rejected_fields"]
    assert "llm_model" in data["fields_updated"]


# ── Provider config SSRF guard ──────────────────────────────────────────

def test_provider_config_rejects_cloud_metadata_url():
    """``169.254.169.254`` (cloud metadata) must be rejected with 400."""
    response = client.post(
        "/api/v1/models/providers/lm_studio/config",
        json={"base_url": "http://169.254.169.254/latest"},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"].lower()


# ── Rate limit headers (slowapi) ────────────────────────────────────────

def test_rate_limit_headers_present():
    """Slowapi must attach X-RateLimit-* headers when headers_enabled=True."""
    with patch("app.state.lm_client") as mock_lm:
        mock_lm.check_health = AsyncMock(return_value=True)
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={
                "vram_total_mb": 1000, "vram_used_mb": 500,
                "vram_used_pct": 50.0, "gpu_available": True,
            })
            response = client.get("/api/v1/health")
    # Slowapi emits lowercase headers via its middleware
    assert "x-ratelimit-limit" in response.headers
    assert "x-ratelimit-remaining" in response.headers
    assert int(response.headers["x-ratelimit-limit"]) >= 1


# ── Provider config keyring migration ──────────────────────────────────

def test_provider_config_stores_api_key_in_keyring_not_env(tmp_path, monkeypatch):
    """An api_key submitted to provider config must NOT land in .env on disk.

    We point CWD at a fresh temp dir so the test cannot pollute or be
    polluted by a real ``.env``. The keyring backend is force-enabled
    so the write path runs end-to-end.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    # Patch the alias imported in the router module too
    from app.routers import system as system_mod
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)
    # Clean up any leftover test entry
    try:
        secrets_mod.delete_secret("OPENAI_API_KEY")
    except Exception:
        pass

    response = client.post(
        "/api/v1/models/providers/openai/config",
        json={"api_key": "sk-leak-test", "base_url": "https://api.openai.com"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert response.json()["stored_in"] == "keyring"
    assert "OPENAI_API_KEY" in response.json()["updated_keys"]

    # The .env file (if created) must NOT contain the API key.
    env_file = tmp_path / ".env"
    if env_file.exists():
        env_text = env_file.read_text(encoding="utf-8")
        assert "sk-leak-test" not in env_text
        assert "OPENAI_API_KEY=sk-leak-test" not in env_text

    # The keyring SHOULD now hold the value.
    assert secrets_mod.get_secret("OPENAI_API_KEY") == "sk-leak-test"

    # Cleanup
    secrets_mod.delete_secret("OPENAI_API_KEY")
    os.environ.pop("OPENAI_API_KEY", None)


def test_provider_config_returns_503_when_keyring_unavailable(monkeypatch):
    """If no keyring backend is available, the endpoint must refuse plaintext."""
    from app.routers import system as system_mod
    monkeypatch.setattr(system_mod, "secrets_available", lambda: False)

    response = client.post(
        "/api/v1/models/providers/openai/config",
        json={"api_key": "sk-should-not-be-saved"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "KeyringUnavailable"
    # Critically, the secret must not be in os.environ either
    assert os.environ.get("OPENAI_API_KEY") != "sk-should-not-be-saved"

