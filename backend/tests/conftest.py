"""Shared pytest fixtures for UDIP backend tests.

Initialises real services (LM Studio, VRAM monitor, etc.) so every
test hits actual hardware and live LLM endpoints.
"""

import os

os.environ["WS_AUTH_TOKEN"] = ""
os.environ["UDIP_ALLOW_LOCAL_LLM"] = "1"

from app.config import get_settings

get_settings.cache_clear()

import app.main as _main

_main.settings.ws_auth_token = ""

import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
async def _init_real_state():
    """Create real services on app.state for every test."""
    from app import state
    from app.dependencies import container
    from app.services.benchmark_runner import BenchmarkRunner
    from app.services.deep_research import DeepResearchService
    from app.services.embedding_service import EmbeddingService
    from app.services.lm_studio_client import LMStudioClient
    from app.services.model_discovery import ModelDiscoveryService
    from app.services.model_manager import ModelManager
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from app.services.text_chunker import TextChunker
    from app.services.vector_kb import VectorKBService
    from app.services.vram_monitor import VRAMMonitor

    originals = {}
    for attr in (
        "lm_client", "vram_monitor", "model_manager", "model_discovery",
        "pageindex_generator", "embedding_service", "text_chunker",
        "vector_kb_service", "deep_research_service", "benchmark_runner",
        "memory_service",
    ):
        originals[attr] = getattr(state, attr, None)

    state.vram_monitor = VRAMMonitor()
    state.lm_client = LMStudioClient(metrics_callback=state.update_metrics)
    state.model_manager = ModelManager(state.lm_client)
    state.model_discovery = ModelDiscoveryService(state.lm_client)
    state.pageindex_generator = PageIndexTreeGenerator(state.lm_client)
    state.benchmark_runner = BenchmarkRunner(
        state.lm_client, state.vram_monitor, state.model_manager
    )
    state.embedding_service = EmbeddingService(state.lm_client, batch_size=32)
    state.text_chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    state.deep_research_service = DeepResearchService(lm_client=state.lm_client)
    state.vector_kb_service = VectorKBService(
        kb_base=Path("data/knowledge_bases"), lm_client=state.lm_client
    )

    container.register("lm_client", lambda: state.lm_client, singleton=True)
    container.register("vram_monitor", lambda: state.vram_monitor, singleton=True)
    container.register("model_manager", lambda: state.model_manager, singleton=True)

    state._startup_time = time.time()
    await state.vram_monitor.initialize()

    settings = get_settings()
    if settings.memory_enabled:
        from app.services.memory_service import MemoryService

        state.memory_service = MemoryService(db_path=settings.memory_db_path)
        container.register("memory_service", lambda: state.memory_service, singleton=True)
        await state.memory_service.initialize()

    yield state

    if state.memory_service:
        try:
            await state.memory_service.close()
        except Exception:
            pass

    for attr, orig in originals.items():
        setattr(state, attr, orig)
