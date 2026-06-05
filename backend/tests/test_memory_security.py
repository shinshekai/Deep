import pytest
from app.services.memory_service import MemoryService


@pytest.fixture
async def svc(tmp_path):
    service = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await service.initialize()
    yield service
    await service.close()


@pytest.mark.asyncio
async def test_sql_injection_episode(svc):
    malicious_query = "'; DROP TABLE episodes; --"
    episode_id = await svc.store_episode(
        device_id="dev1",
        query=malicious_query,
        answer="test answer",
        agents=["solve"],
        model_used="test",
    )
    assert episode_id is not None
    episodes = await svc.list_episodes("dev1")
    assert len(episodes) == 1
    assert episodes[0]["query"] == malicious_query
    stats = await svc.get_stats()
    assert stats["episodes_total"] >= 1


@pytest.mark.asyncio
async def test_sql_injection_fact(svc):
    malicious_content = "'; DROP TABLE facts; --"
    fact_id = await svc.store_fact(
        device_id="dev1",
        content=malicious_content,
        source_type="conversation",
    )
    assert fact_id is not None
    facts = await svc.recall_facts("dev1", malicious_content)
    assert len(facts) >= 1


@pytest.mark.asyncio
async def test_device_isolation_episodes(svc):
    await svc.store_episode(device_id="dev_a", query="secret A", answer="answer A")
    await svc.store_episode(device_id="dev_b", query="secret B", answer="answer B")
    episodes_a = await svc.list_episodes("dev_a")
    episodes_b = await svc.list_episodes("dev_b")
    assert len(episodes_a) == 1
    assert len(episodes_b) == 1
    assert episodes_a[0]["query"] == "secret A"
    assert episodes_b[0]["query"] == "secret B"


@pytest.mark.asyncio
async def test_device_isolation_facts(svc):
    await svc.store_fact(device_id="dev_a", content="fact A")
    await svc.store_fact(device_id="dev_b", content="fact B")
    facts_a = await svc.recall_facts("dev_a", "fact")
    facts_b = await svc.recall_facts("dev_b", "fact")
    assert all(f["device_id"] == "dev_a" for f in facts_a)
    assert all(f["device_id"] == "dev_b" for f in facts_b)


@pytest.mark.asyncio
async def test_device_isolation_profile(svc):
    await svc.update_profile("dev_a", {"preference": "dark_mode"})
    await svc.update_profile("dev_b", {"preference": "light_mode"})
    profile_a = await svc.get_profile("dev_a")
    profile_b = await svc.get_profile("dev_b")
    assert profile_a.get("preference") == "dark_mode"
    assert profile_b.get("preference") == "light_mode"


@pytest.mark.asyncio
async def test_empty_device_returns_empty(svc):
    episodes = await svc.list_episodes("nonexistent")
    facts = await svc.recall_facts("nonexistent", "test")
    profile = await svc.get_profile("nonexistent")
    stats = await svc.get_stats()
    assert episodes == []
    assert facts == []
    assert profile["device_id"] == "nonexistent"
    assert stats["episodes_total"] == 0


@pytest.mark.asyncio
async def test_special_characters_in_query(svc):
    special_queries = [
        "SELECT * FROM episodes",
        "admin'--",
        "\" OR \"1\"=\"1",
        "'; INSERT INTO episodes VALUES('hack'); --",
        "日本語テスト",
        "emoji 🧠💻🔒",
    ]
    for q in special_queries:
        episode_id = await svc.store_episode(device_id="dev1", query=q, answer="test")
        assert episode_id is not None
    episodes = await svc.list_episodes("dev1")
    assert len(episodes) == len(special_queries)
