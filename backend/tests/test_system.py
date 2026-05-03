import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    with patch("app.state.lm_client") as mock_lm:
        mock_lm.check_health = AsyncMock(return_value=True)
        with patch("app.state.vram_monitor") as mock_vm:
            mock_vm.poll_once = AsyncMock(return_value={"vram_total_mb": 1000, "vram_used_mb": 500})
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert "status" in response.json()

def test_config_endpoint():
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    assert "llm_host" in response.json()

