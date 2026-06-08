from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_memory_service():
    svc = MagicMock()
    svc.recall_episodes = AsyncMock(return_value=[])
    svc.recall_facts = AsyncMock(return_value=[])
    svc.get_profile = AsyncMock(return_value={"device_id": "test", "profile": {}})
    svc.update_profile = AsyncMock(return_value={"profile": {}})
    svc.store_episode = AsyncMock(return_value="ep_123")
    svc.store_fact = AsyncMock(return_value="fact_123")
    svc.list_episodes = AsyncMock(return_value=[])
    svc.delete_episode = AsyncMock(return_value=True)
    svc.get_stats = AsyncMock(return_value={"episodes": 0, "facts": 0, "profiles": 0})
    svc.decay_old_facts = AsyncMock(return_value=0)
    svc.compact_episodes = AsyncMock(return_value=0)
    return svc


@pytest.fixture(autouse=True)
def inject_memory_service(mock_memory_service):
    import app.state as state_module

    state_module.memory_service = mock_memory_service
    yield
    state_module.memory_service = None


@pytest.mark.asyncio
async def test_recall_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/recall", json={"query": "test", "device_id": "dev1"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "episodes" in data
    assert "facts" in data


@pytest.mark.asyncio
async def test_profile_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/profile/dev1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "dev1"


@pytest.mark.asyncio
async def test_store_episode_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/episode",
            json={
                "device_id": "dev1",
                "query": "test",
                "answer": "answer",
                "agents": ["solve"],
                "model_used": "m",
                "session_type": "chat",
            },
        )
    assert resp.status_code == 200
    assert "episode_id" in resp.json()


@pytest.mark.asyncio
async def test_stats_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/stats/dev1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_episodes_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/episodes/dev1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_episode_endpoint(mock_memory_service):
    mock_memory_service.get_episode = AsyncMock(return_value={"id": "ep_123", "device_id": "dev1"})
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/v1/memory/episode/ep_123?device_id=dev1")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_submit_feedback_endpoint(mock_memory_service):
    mock_memory_service.get_episode = AsyncMock(return_value={"id": "ep_123", "device_id": "dev1"})
    mock_db = AsyncMock()
    mock_memory_service._get_db = AsyncMock(return_value=mock_db)
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/feedback",
            json={"episode_id": "ep_123", "device_id": "dev1", "rating": 4.5},
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_fact_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/fact",
            json={
                "device_id": "dev1",
                "content": "fact content",
                "source_type": "conversation",
                "source_id": "s1",
            },
        )
    assert resp.status_code == 200
    assert "fact_id" in resp.json()


@pytest.mark.asyncio
async def test_list_facts_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/facts/dev1")
    assert resp.status_code == 200
    assert "facts" in resp.json()


@pytest.mark.asyncio
async def test_decay_endpoint(mock_memory_service):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/memory/decay")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_service_unavailable():
    import app.state as state_module

    state_module.memory_service = None
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/recall", json={"query": "test", "device_id": "dev1"}
        )
    assert resp.status_code == 503
