"""Unit tests for memory_consolidator.py — LLM-driven consolidation."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.memory_consolidator import MemoryConsolidator


class TestMemoryConsolidator:
    @pytest.fixture
    def mock_memory(self):
        mem = AsyncMock()
        mem.crystallize_observations = AsyncMock(return_value=5)
        mem.get_staged_observations = AsyncMock(return_value=[
            {"source_type": "solve", "content": "User asked about Python async patterns"},
            {"source_type": "solve", "content": "User prefers concise answers"},
        ])
        mem.store_fact = AsyncMock()
        mem.get_l3_all = AsyncMock(return_value={
            "profile": "Python developer, prefers concise answers",
            "topics": "software engineering",
        })
        return mem

    @pytest.fixture
    def mock_lm(self):
        lm = AsyncMock()
        lm.stream_chat_completion = AsyncMock(return_value={
            "content": '{"profile": "Python developer who prefers concise answers"}',
        })
        return lm

    @pytest.mark.asyncio
    async def test_update_mode_processes_observations(self, mock_memory, mock_lm):
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="update")

        assert result["mode"] == "update"
        assert result["observations_processed"] == 5
        mock_memory.crystallize_observations.assert_called_once_with("device-1")
        mock_memory.store_fact.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_mode_no_observations(self, mock_memory, mock_lm):
        mock_memory.crystallize_observations.return_value = 0
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="update")

        assert result["observations_processed"] == 0

    @pytest.mark.asyncio
    async def test_dedup_mode(self, mock_memory, mock_lm):
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="dedup")

        assert result["mode"] == "dedup"
        assert "pairs_checked" in result

    @pytest.mark.asyncio
    async def test_audit_mode(self, mock_memory, mock_lm):
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="audit")

        assert result["mode"] == "audit"
        assert "verified" in result

    @pytest.mark.asyncio
    async def test_merge_mode(self, mock_memory, mock_lm):
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="merge")

        assert result["mode"] == "merge"

    @pytest.mark.asyncio
    async def test_unknown_mode(self, mock_memory, mock_lm):
        consolidator = MemoryConsolidator(mock_memory, mock_lm)
        result = await consolidator.consolidate("device-1", "test-model", mode="unknown")

        assert "error" in result
