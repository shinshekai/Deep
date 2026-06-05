import pytest
import asyncio
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock


class TestAgentOutcomes:
    @pytest.mark.asyncio
    async def test_record_and_retrieve_outcome(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            await svc.record_agent_outcome(
                agent_type="solve", query_pattern="python error",
                strategy="retry with fallback", outcome_quality=0.85,
                model_used="test-model", tier=1, device_id="dev1",
            )

            strategies = await svc.get_agent_strategies("solve")
            assert len(strategies) >= 1
            assert strategies[0]["best_strategy"] == "retry with fallback"
            assert strategies[0]["sample_count"] == 1

            await svc.close()

    @pytest.mark.asyncio
    async def test_strategy_learning_updates_best(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            await svc.record_agent_outcome(
                agent_type="solve", query_pattern="deploy",
                strategy="docker", outcome_quality=0.6,
            )
            await svc.record_agent_outcome(
                agent_type="solve", query_pattern="deploy",
                strategy="kubernetes", outcome_quality=0.9,
            )

            strategies = await svc.get_agent_strategies("solve", "deploy")
            assert len(strategies) >= 1
            assert strategies[0]["best_strategy"] == "kubernetes"
            assert strategies[0]["sample_count"] == 2

            await svc.close()

    @pytest.mark.asyncio
    async def test_agent_outcome_isolation_by_type(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            await svc.record_agent_outcome(
                agent_type="solve", query_pattern="q1",
                strategy="s1", outcome_quality=0.8,
            )
            await svc.record_agent_outcome(
                agent_type="research", query_pattern="q1",
                strategy="s2", outcome_quality=0.7,
            )

            solve_strats = await svc.get_agent_strategies("solve")
            research_strats = await svc.get_agent_strategies("research")
            assert len(solve_strats) >= 1
            assert len(research_strats) >= 1
            assert solve_strats[0]["agent_type"] == "solve"
            assert research_strats[0]["agent_type"] == "research"

            await svc.close()


class TestMemoryMaintenance:
    @pytest.mark.asyncio
    async def test_decay_reduces_confidence(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            fid = await svc.store_fact("dev1", "Test fact", "conversation", confidence=0.8)

            db = await svc._get_db()
            old_time = asyncio.get_event_loop().time() - 40 * 86400
            await db.execute("UPDATE facts SET created_at = ? WHERE id = ?", (old_time, fid))
            await db.commit()

            decayed = await svc.decay_old_facts(days=30, decay_rate=0.1)
            assert decayed >= 1

            facts = await svc.recall_facts("dev1", "Test fact")
            if facts:
                assert facts[0]["confidence"] < 0.8

            await svc.close()

    @pytest.mark.asyncio
    async def test_compact_archives_old_episodes(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            eid = await svc.store_episode("dev1", "Old query", "Old answer", session_type="chat")

            db = await svc._get_db()
            old_time = asyncio.get_event_loop().time() - 100 * 86400
            await db.execute(
                "UPDATE episodes SET created_at = ?, outcome_rating = 0.1 WHERE id = ?",
                (old_time, eid),
            )
            await db.commit()

            compacted = await svc.compact_episodes(older_than_days=90)
            assert compacted >= 1

            await svc.close()

    @pytest.mark.asyncio
    async def test_stats_after_operations(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            await svc.store_episode("dev1", "q1", "a1", session_type="chat")
            await svc.store_fact("dev1", "fact1", "conversation")
            await svc.record_agent_outcome("solve", "pattern1", "strategy1", 0.8)

            stats = await svc.get_stats("dev1")
            assert stats["episodes"] >= 1
            assert stats["facts"] >= 1

            global_stats = await svc.get_stats()
            assert "episodes_total" in global_stats
            assert "agent_outcomes" in global_stats

            await svc.close()


class TestProjectProfiles:
    @pytest.mark.asyncio
    async def test_project_profile_create_and_update(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            await svc.update_project_profile("my_kb", {
                "themes": ["AI", "ML"],
                "document_count": 5,
                "total_pages": 100,
            })

            profile = await svc.get_project_profile("my_kb")
            assert profile is not None
            assert profile["kb_name"] == "my_kb"
            assert "AI" in profile.get("themes", [])

            await svc.update_project_profile("my_kb", {
                "themes": ["AI", "ML", "DL"],
                "document_count": 8,
            })

            profile2 = await svc.get_project_profile("my_kb")
            assert profile2["document_count"] == 8

            await svc.close()

    @pytest.mark.asyncio
    async def test_project_profile_null_for_missing(self):
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(db_path=os.path.join(tmp, "test.db"))
            await svc.initialize()

            profile = await svc.get_project_profile("nonexistent")
            assert profile is None

            await svc.close()


class TestMigration:
    def test_scan_solve_sessions_empty(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from migrate_to_memory import scan_solve_sessions
        with tempfile.TemporaryDirectory() as tmp:
            result = scan_solve_sessions(tmp)
            assert result == []

    def test_scan_solve_sessions_finds_files(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from migrate_to_memory import scan_solve_sessions
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "user" / "solve" / "test_session"
            session_dir.mkdir(parents=True)
            (session_dir / "final_answer.md").write_text("Test answer")
            (session_dir / "transcript.md").write_text("## Query\nWhat is Python?\n\n## Notes")

            result = scan_solve_sessions(tmp)
            assert len(result) == 1
            assert "Python" in result[0]["query"]

    def test_scan_research_sessions_empty(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from migrate_to_memory import scan_research_sessions
        with tempfile.TemporaryDirectory() as tmp:
            result = scan_research_sessions(tmp)
            assert result == []

    def test_guide_sessions_empty(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from migrate_to_memory import scan_guide_sessions
        with tempfile.TemporaryDirectory() as tmp:
            result = scan_guide_sessions(tmp)
            assert result == []


class TestMemoryMaintenanceModule:
    def test_import(self):
        from app.services.memory_maintenance import memory_maintenance_loop
        assert callable(memory_maintenance_loop)

    @pytest.mark.asyncio
    async def test_loop_runs_once(self):
        from app.services.memory_maintenance import memory_maintenance_loop
        mock_svc = AsyncMock()
        mock_svc.decay_old_facts = AsyncMock(return_value=0)
        mock_svc.compact_episodes = AsyncMock(return_value=0)
        mock_svc.get_memory_stats_summary = AsyncMock(return_value={"episodes": 0, "facts": 0})

        async def run_once():
            task = asyncio.create_task(memory_maintenance_loop(mock_svc, interval=0.01))
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_once()
        mock_svc.decay_old_facts.assert_called()
        mock_svc.compact_episodes.assert_called()
