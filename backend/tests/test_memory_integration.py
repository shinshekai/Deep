import pytest
import json
from unittest.mock import AsyncMock

from app.services.memory_context import build_memory_context
from app.services.memory_service import MemoryService


class TestMemoryContextBuilder:
    def test_build_empty_context(self):
        ctx = build_memory_context(None, [], [])
        assert ctx == ""

    def test_build_with_profile(self):
        profile = {
            "device_id": "dev1",
            "profile": {
                "static": {"role": "developer", "expertise": "Python"},
                "dynamic": {"recent_topics": ["fastapi", "sqlite"]},
            },
        }
        ctx = build_memory_context(profile, [], [])
        assert "developer" in ctx
        assert "Python" in ctx
        assert "fastapi" in ctx

    def test_build_with_episodes(self):
        episodes = [
            {"query": "What is FastAPI?", "answer": "A Python web framework.", "session_type": "chat", "score": 0.9},
            {"query": "How to deploy?", "answer": "Use Docker.", "session_type": "solve", "score": 0.7},
        ]
        ctx = build_memory_context(None, episodes, [])
        assert "FastAPI" in ctx
        assert "Docker" in ctx
        assert "Past Conversations" in ctx

    def test_build_with_facts(self):
        facts = [
            {"content": "Python was created by Guido", "confidence": 0.95},
            {"content": "SQLite is serverless", "confidence": 0.8},
            {"content": "Uncertain fact", "confidence": 0.2},
        ]
        ctx = build_memory_context(None, [], facts)
        assert "Guido" in ctx
        assert "SQLite" in ctx
        assert "Uncertain fact" not in ctx

    def test_token_budget_enforced(self):
        episodes = [
            {"query": f"query {i}", "answer": f"answer {i} " * 50, "session_type": "chat"}
            for i in range(20)
        ]
        ctx = build_memory_context(None, episodes, [], token_budget=200)
        assert len(ctx) < 5000

    def test_build_with_agent_strategies(self):
        strategies = [
            {"agent_type": "solve", "best_strategy": "step-by-step", "success_rate": 0.85},
        ]
        ctx = build_memory_context(None, [], [], agent_strategies=strategies)
        assert "step-by-step" in ctx
        assert "85%" in ctx

    def test_profile_without_dynamic_topics(self):
        profile = {
            "device_id": "dev1",
            "profile": {"static": {"role": "student"}, "dynamic": {}},
        }
        ctx = build_memory_context(profile, [], [])
        assert "student" in ctx

    def test_episodes_limited_to_five(self):
        episodes = [{"query": f"q{i}", "answer": f"a{i}", "session_type": "chat"} for i in range(10)]
        ctx = build_memory_context(None, episodes, [], token_budget=50000)
        assert ctx.count("[chat]") <= 5

    def test_facts_with_empty_profile_key(self):
        profile = {"device_id": "dev1"}
        ctx = build_memory_context(profile, [], [])
        assert ctx == ""

    def test_build_all_sections_combined(self):
        profile = {
            "device_id": "dev1",
            "profile": {
                "static": {"role": "engineer"},
                "dynamic": {"recent_topics": ["rust"]},
            },
        }
        episodes = [{"query": "What is Rust?", "answer": "A systems language.", "session_type": "chat"}]
        facts = [{"content": "Rust has no GC", "confidence": 0.9}]
        strategies = [{"agent_type": "solve", "best_strategy": "borrow checker tips", "success_rate": 0.7}]
        ctx = build_memory_context(profile, episodes, facts, agent_strategies=strategies)
        assert "engineer" in ctx
        assert "Rust" in ctx
        assert "borrow checker" in ctx


class TestFactExtractorParsing:
    def test_parse_json_array(self):
        raw = json.dumps([{"content": "Python is interpreted", "confidence": 0.9}])
        facts = json.loads(raw)
        assert len(facts) == 1
        assert facts[0]["content"] == "Python is interpreted"

    def test_parse_markdown_code_block(self):
        raw = '```json\n[{"content": "Test fact", "confidence": 0.7}]\n```'
        cleaned = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        facts = json.loads(cleaned)
        assert len(facts) == 1

    def test_parse_empty_array(self):
        facts = json.loads("[]")
        assert facts == []

    def test_parse_non_list_returns_empty(self):
        raw = '{"content": "single object"}'
        data = json.loads(raw)
        assert not isinstance(data, list)

    @pytest.mark.asyncio
    async def test_extract_no_answer_returns_empty(self):
        from app.services.fact_extractor import extract_and_store_facts
        result = await extract_and_store_facts("dev1", "query", "", "src", None, None)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_llm_error_returns_empty(self):
        from app.services.fact_extractor import extract_and_store_facts
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={"error": "fail"})
        result = await extract_and_store_facts("dev1", "query", "answer", "src", mock_lm, None)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_invalid_json_returns_empty(self):
        from app.services.fact_extractor import extract_and_store_facts
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={"content": "not json"})
        result = await extract_and_store_facts("dev1", "query", "answer", "src", mock_lm, None)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_strips_code_fence(self):
        from app.services.fact_extractor import extract_and_store_facts
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": '```json\n[{"content": "Fact one", "confidence": 0.8}]\n```'
        })
        mock_mem = AsyncMock()
        mock_mem.store_fact = AsyncMock(return_value="f1")
        result = await extract_and_store_facts("dev1", "q", "a", "src", mock_lm, mock_mem)
        assert len(result) == 1
        mock_mem.store_fact.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_stores_multiple_facts(self):
        from app.services.fact_extractor import extract_and_store_facts
        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": json.dumps([
                {"content": "Fact A", "confidence": 0.9},
                {"content": "Fact B", "confidence": 0.7},
                {"content": "", "confidence": 0.5},
            ])
        })
        mock_mem = AsyncMock()
        mock_mem.store_fact = AsyncMock(side_effect=["f1", "f2"])
        result = await extract_and_store_facts("dev1", "q", "a", "src", mock_lm, mock_mem)
        assert len(result) == 2
        assert mock_mem.store_fact.call_count == 2


class TestMemoryPipeline:
    @pytest.fixture
    async def memory_service(self, tmp_path):
        svc = MemoryService(db_path=str(tmp_path / "test.db"))
        await svc.initialize()
        yield svc
        await svc.close()

    @pytest.mark.asyncio
    async def test_recall_then_store_episode(self, memory_service):
        eid = await memory_service.store_episode(
            "dev1", "What is Python?", "A programming language.", session_type="chat"
        )
        assert eid is not None

        results = await memory_service.recall_episodes("dev1", "Python programming")
        assert len(results) >= 1
        assert "Python" in results[0]["query"]

        fid = await memory_service.store_fact(
            "dev1", "Python is interpreted", "conversation", confidence=0.9
        )
        assert fid is not None

        facts = await memory_service.recall_facts("dev1", "Is Python interpreted?")
        assert len(facts) >= 1

        profile = await memory_service.update_profile(
            "dev1", {"type": "learning_started", "topic": "Python"}
        )
        assert profile is not None

        profile2 = await memory_service.get_profile("dev1")
        assert profile2["device_id"] == "dev1"

        stats = await memory_service.get_stats("dev1")
        assert stats["episodes"] >= 1
        assert stats["facts"] >= 1

    @pytest.mark.asyncio
    async def test_memory_context_builds_from_service(self, memory_service):
        await memory_service.store_episode(
            "dev1", "How to learn Python?", "Practice daily.", session_type="learning"
        )
        await memory_service.store_fact(
            "dev1", "Python has list comprehensions", "conversation", confidence=0.95
        )

        episodes = await memory_service.recall_episodes("dev1", "learn Python")
        facts = await memory_service.recall_facts("dev1", "Python")

        ctx = build_memory_context(None, episodes, facts)
        assert "Python" in ctx
        assert len(ctx) > 50

    @pytest.mark.asyncio
    async def test_cross_session_memory(self, memory_service):
        await memory_service.store_episode(
            "dev1", "What is FastAPI?", "A Python web framework.", session_type="chat"
        )
        await memory_service.store_episode(
            "dev1", "How to deploy FastAPI apps?", "Use Docker containers.", session_type="solve"
        )

        results = await memory_service.recall_episodes("dev1", "FastAPI")
        assert len(results) >= 1

        results_dev2 = await memory_service.recall_episodes("dev2", "FastAPI")
        assert len(results_dev2) == 0

    @pytest.mark.asyncio
    async def test_fact_extraction_pipeline(self, memory_service):
        from app.services.fact_extractor import extract_and_store_facts

        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": json.dumps([
                {"content": "Python is dynamically typed", "confidence": 0.9},
                {"content": "Python supports multiple paradigms", "confidence": 0.85},
            ])
        })

        result = await extract_and_store_facts(
            "dev1", "Tell me about Python", "Python is a versatile language.",
            "session_1", mock_lm, memory_service
        )
        assert len(result) == 2

        facts = await memory_service.recall_facts("dev1", "Python")
        assert len(facts) >= 1

    @pytest.mark.asyncio
    async def test_agent_strategy_and_context(self, memory_service):
        await memory_service.record_agent_outcome(
            agent_type="solve", query_pattern="python.*error",
            strategy="step-by-step debugging", outcome_quality=0.9,
            model_used="test-model", tier=1, device_id="dev1"
        )

        strategies = await memory_service.get_agent_strategies("solve", "python.*error")
        assert len(strategies) >= 1
        assert strategies[0]["best_strategy"] == "step-by-step debugging"

        ctx = build_memory_context(None, [], [], agent_strategies=strategies)
        assert "step-by-step" in ctx

    @pytest.mark.asyncio
    async def test_contradiction_detection(self, memory_service):
        await memory_service.store_fact(
            "dev1", "Python is a compiled language", "conversation", confidence=0.8
        )
        contradictions = await memory_service.detect_contradictions(
            "Python is not a compiled language", "dev1"
        )
        assert isinstance(contradictions, list)

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, memory_service):
        from app.services.fact_extractor import extract_and_store_facts

        mock_lm = AsyncMock()
        mock_lm.stream_chat_completion = AsyncMock(return_value={
            "content": json.dumps([{"content": "FastAPI uses async/await", "confidence": 0.95}])
        })

        await memory_service.store_episode(
            "dev1", "What is FastAPI?", "A modern Python web framework.", session_type="chat"
        )
        await extract_and_store_facts(
            "dev1", "What is FastAPI?", "FastAPI uses async/await for high performance.",
            "ep_1", mock_lm, memory_service
        )
        await memory_service.update_profile(
            "dev1", {"type": "learning_started", "topic": "FastAPI"}
        )
        await memory_service.record_agent_outcome(
            agent_type="solve", query_pattern="fastapi.*question",
            strategy="provide example code", outcome_quality=0.85, device_id="dev1"
        )

        episodes = await memory_service.recall_episodes("dev1", "FastAPI")
        facts = await memory_service.recall_facts("dev1", "FastAPI async")
        profile = await memory_service.get_profile("dev1")
        strategies = await memory_service.get_agent_strategies("solve")

        ctx = build_memory_context(profile, episodes, facts, agent_strategies=strategies)
        assert "FastAPI" in ctx
        assert "async" in ctx

        stats = await memory_service.get_stats("dev1")
        assert stats["episodes"] >= 1
        assert stats["facts"] >= 1
