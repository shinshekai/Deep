import pytest
from pathlib import Path

from app.services.memory_service import MemoryService


@pytest.fixture
async def memory_service(tmp_path):
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    yield svc
    await svc.close()


class TestEpisodicMemory:
    async def test_store_and_retrieve_episode(self, memory_service):
        eid = await memory_service.store_episode(
            device_id="dev1", query="What is Python?",
            answer="Python is a programming language.",
            agents=["solve"], model_used="test-model", session_type="solve"
        )
        assert eid is not None
        assert len(eid) > 0

    async def test_recall_returns_relevant_episodes(self, memory_service):
        await memory_service.store_episode("dev1", "What is Python?", "A language.", session_type="chat")
        await memory_service.store_episode("dev1", "How does photosynthesis work?", "Light energy.", session_type="chat")
        results = await memory_service.recall_episodes("dev1", "Python")
        assert len(results) >= 1
        assert any("Python" in r["query"] for r in results)

    async def test_list_episodes(self, memory_service):
        for i in range(5):
            await memory_service.store_episode("dev1", f"query {i}", f"answer {i}", session_type="chat")
        result = await memory_service.list_episodes("dev1", limit=3)
        assert len(result) == 3

    async def test_delete_episode(self, memory_service):
        eid = await memory_service.store_episode("dev1", "test", "answer", session_type="chat")
        deleted = await memory_service.delete_episode(eid)
        assert deleted is True
        episode = await memory_service.get_episode(eid)
        assert episode is None

    async def test_device_isolation(self, memory_service):
        await memory_service.store_episode("dev1", "query1", "answer1", session_type="chat")
        await memory_service.store_episode("dev2", "query2", "answer2", session_type="chat")
        dev1_episodes = await memory_service.recall_episodes("dev1", "query")
        dev2_episodes = await memory_service.recall_episodes("dev2", "query")
        assert all(e["device_id"] == "dev1" for e in dev1_episodes)
        assert all(e["device_id"] == "dev2" for e in dev2_episodes)

    async def test_get_episode(self, memory_service):
        eid = await memory_service.store_episode("dev1", "q", "a", session_type="chat")
        episode = await memory_service.get_episode(eid)
        assert episode is not None
        assert episode["query"] == "q"
        assert episode["answer"] == "a"
        assert episode["device_id"] == "dev1"

    async def test_get_nonexistent_episode(self, memory_service):
        episode = await memory_service.get_episode("nonexistent")
        assert episode is None

    async def test_list_episodes_with_offset(self, memory_service):
        for i in range(5):
            await memory_service.store_episode("dev1", f"q{i}", f"a{i}", session_type="chat")
        page1 = await memory_service.list_episodes("dev1", limit=2, offset=0)
        page2 = await memory_service.list_episodes("dev1", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]

    async def test_store_episode_with_citations(self, memory_service):
        eid = await memory_service.store_episode(
            "dev1", "q", "a", citations=[{"url": "http://example.com"}], session_type="chat"
        )
        episode = await memory_service.get_episode(eid)
        assert episode["citations"] == [{"url": "http://example.com"}]


class TestFactMemory:
    async def test_store_and_recall_facts(self, memory_service):
        fid = await memory_service.store_fact("dev1", "Python was created by Guido van Rossum", "conversation")
        assert fid is not None
        facts = await memory_service.recall_facts("dev1", "Who created Python?")
        assert len(facts) >= 1

    async def test_detect_contradictions(self, memory_service):
        await memory_service.store_fact("dev1", "Python is a compiled language", "conversation", confidence=0.8)
        contradictions = await memory_service.detect_contradictions("Python is an interpreted language", "dev1")
        assert isinstance(contradictions, list)

    async def test_store_fact_with_confidence(self, memory_service):
        fid = await memory_service.store_fact("dev1", "fact content", "test", confidence=0.9)
        assert fid is not None
        facts = await memory_service.recall_facts("dev1", "fact")
        assert len(facts) >= 1
        assert facts[0]["confidence"] == 0.9

    async def test_recall_facts_empty(self, memory_service):
        facts = await memory_service.recall_facts("dev1", "nonexistent")
        assert facts == []


class TestUserProfile:
    async def test_get_empty_profile(self, memory_service):
        profile = await memory_service.get_profile("dev1")
        assert profile is not None
        assert profile["device_id"] == "dev1"

    async def test_update_profile(self, memory_service):
        updated = await memory_service.update_profile("dev1", {"type": "learning_started", "topic": "Python"})
        assert updated is not None
        assert updated["type"] == "learning_started"

    async def test_profile_persists_across_updates(self, memory_service):
        await memory_service.update_profile("dev1", {"a": 1})
        await memory_service.update_profile("dev1", {"b": 2})
        profile = await memory_service.get_profile("dev1")
        assert profile["a"] == 1
        assert profile["b"] == 2


class TestAgentMemory:
    async def test_record_and_retrieve_outcome(self, memory_service):
        await memory_service.record_agent_outcome(
            agent_type="solve", query_pattern="python.*error",
            strategy="retry with different model", outcome_quality=0.8,
            model_used="test", tier=1, device_id="dev1"
        )
        strategies = await memory_service.get_agent_strategies("solve", "python.*error")
        assert isinstance(strategies, list)
        assert len(strategies) >= 1

    async def test_agent_strategy_updates(self, memory_service):
        await memory_service.record_agent_outcome(
            agent_type="chat", query_pattern="greeting",
            strategy="friendly", outcome_quality=0.9, device_id="dev1"
        )
        await memory_service.record_agent_outcome(
            agent_type="chat", query_pattern="greeting",
            strategy="formal", outcome_quality=0.6, device_id="dev1"
        )
        strategies = await memory_service.get_agent_strategies("chat", "greeting")
        assert len(strategies) == 1
        assert strategies[0]["best_strategy"] == "friendly"

    async def test_get_agent_strategies_by_type(self, memory_service):
        await memory_service.record_agent_outcome(
            agent_type="solve", query_pattern="p1",
            strategy="s1", outcome_quality=0.7, device_id="dev1"
        )
        strategies = await memory_service.get_agent_strategies("solve")
        assert len(strategies) >= 1


class TestProjectMemory:
    async def test_project_profile(self, memory_service):
        await memory_service.update_project_profile("my_kb", {"themes": ["AI", "ML"], "document_count": 10})
        profile = await memory_service.get_project_profile("my_kb")
        assert profile is not None
        assert profile["kb_name"] == "my_kb"

    async def test_project_profile_nonexistent(self, memory_service):
        profile = await memory_service.get_project_profile("no_such_kb")
        assert profile is None

    async def test_project_profile_updates(self, memory_service):
        await memory_service.update_project_profile("kb1", {"themes": ["A"]})
        await memory_service.update_project_profile("kb1", {"themes": ["A", "B"]})
        profile = await memory_service.get_project_profile("kb1")
        assert profile["themes"] == ["A", "B"]


class TestStats:
    async def test_get_stats(self, memory_service):
        await memory_service.store_episode("dev1", "q", "a", session_type="chat")
        stats = await memory_service.get_stats("dev1")
        assert stats["episodes"] >= 1
        assert "facts" in stats

    async def test_get_stats_global(self, memory_service):
        await memory_service.store_episode("dev1", "q", "a", session_type="chat")
        stats = await memory_service.get_stats()
        assert "episodes_total" in stats
        assert "facts_total" in stats


class TestMaintenance:
    async def test_decay_old_facts(self, memory_service):
        decayed = await memory_service.decay_old_facts()
        assert isinstance(decayed, int)

    async def test_compact_episodes(self, memory_service):
        compacted = await memory_service.compact_episodes()
        assert isinstance(compacted, int)


class TestUsageTracking:
    async def test_track_usage(self, memory_service):
        await memory_service.track_usage("dev1", "recalls", 1)
        await memory_service.track_usage("dev1", "recalls", 1)
        usage = await memory_service.get_usage("dev1", "recalls")
        assert len(usage) == 2

    async def test_usage_summary_in_stats(self, memory_service):
        await memory_service.track_usage("dev1", "episodes_stored", 3)
        stats = await memory_service.get_stats("dev1")
        assert "usage_7d" in stats
