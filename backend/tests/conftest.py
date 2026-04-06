"""Shared pytest fixtures."""
import pytest
import httpx


@pytest.fixture
def mock_httpx_response():
    return httpx.Response(200, json={"data": [{"id": "Qwen3-4B-Q4_K_M"}]})
