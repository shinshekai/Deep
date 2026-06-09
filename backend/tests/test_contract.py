"""Contract tests verifying backend API responses match frontend expectations.

These tests document the ACTUAL API contract. Mismatches with frontend
types are flagged as test failures to surface drift.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthContract:
    """Verify health endpoint response matches frontend expectations."""

    def test_health_response_has_required_fields(self):
        response = client.get("/api/v1/health")
        data = response.json()

        assert "status" in data
        assert data["status"] in ("ok", "degraded")

        assert "lm_studio" in data
        assert isinstance(data["lm_studio"], bool)

        assert "gpu" in data

        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

        assert "turboquant_enabled" in data
        assert isinstance(data["turboquant_enabled"], bool)


class TestConfigContract:
    """Verify config endpoint response matches frontend expectations."""

    def test_config_response_has_required_fields(self):
        response = client.get("/api/v1/config")
        data = response.json()

        assert "llm_host" in data
        assert isinstance(data["llm_host"], str)

        assert "llm_port" in data
        assert isinstance(data["llm_port"], int)

        assert "llm_model" in data
        assert isinstance(data["llm_model"], str)

        assert "embedding_host" in data
        assert isinstance(data["embedding_host"], str)

        assert "embedding_model" in data
        assert isinstance(data["embedding_model"], str)

        assert "turboquant_enabled" in data
        assert isinstance(data["turboquant_enabled"], bool)

        assert "turboquant_bits" in data
        assert isinstance(data["turboquant_bits"], int)

        assert "turboquant_tier" in data
        assert isinstance(data["turboquant_tier"], str)

        assert "vram_safety_margin_pct" in data
        assert isinstance(data["vram_safety_margin_pct"], int)

        assert "t2_ttl" in data
        assert isinstance(data["t2_ttl"], int)

        assert "t3_ttl" in data
        assert isinstance(data["t3_ttl"], int)

        assert "enable_thinking" in data
        assert isinstance(data["enable_thinking"], bool)

        assert "backend_port" in data
        assert isinstance(data["backend_port"], int)

        assert "frontend_port" in data
        assert isinstance(data["frontend_port"], int)

        assert "search_provider" in data
        assert isinstance(data["search_provider"], str)


class TestModelsContract:
    """Verify models endpoint responses match frontend expectations."""

    def test_discover_response_structure(self):
        response = client.get("/api/v1/models/discover")
        data = response.json()

        assert "local" in data
        assert isinstance(data["local"], list)

        assert "cloud" in data
        assert isinstance(data["cloud"], list)

        for provider in data["local"]:
            assert "id" in provider
            assert "name" in provider
            assert "status" in provider
            assert "models" in provider
            assert isinstance(provider["models"], list)


class TestSelectModelContract:
    """Verify model selection response matches frontend expectations."""

    def test_select_model_response_structure(self):
        response = client.post(
            "/api/v1/models/select",
            json={
                "provider_type": "local",
                "provider_id": "lm_studio",
                "model_id": "google/gemma-4-e2b",
                "load": False,
            },
        )
        data = response.json()

        assert "selected" in data
        assert isinstance(data["selected"], bool)

        if data["selected"]:
            assert "active_selection" in data
            selection = data["active_selection"]
            assert "model_id" in selection
            assert "provider_type" in selection
            assert "provider_id" in selection


class TestMemoryContract:
    """Verify memory endpoints match frontend expectations."""

    def test_memory_stats_response_structure(self):
        response = client.get("/api/v1/memory/stats")
        if response.status_code == 200:
            data = response.json()
            assert "total_episodes" in data
            assert "total_facts" in data

    def test_memory_episodes_response_structure(self):
        response = client.get("/api/v1/memory/episodes?device_id=test&limit=10")
        if response.status_code == 200:
            data = response.json()
            assert "episodes" in data
            assert isinstance(data["episodes"], list)
