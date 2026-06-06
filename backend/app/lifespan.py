"""Application lifespan — extracted from main.py for modularity.

Manages startup/shutdown of services, background tasks, and the
async context manager passed to FastAPI.
"""

import asyncio
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app import state
from app.dependencies import container
from app.websocket_handlers import broadcast_loop, ttl_loop
from app.services.task_registry import TaskRegistry, _global_registry
from app.services.task_wal import TaskWAL

logger = logging.getLogger(__name__)

_lifespan_registry = TaskRegistry(name="lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    state._startup_time = time.time()
    logger.info("Starting UDIP Backend on :8001")

    from app.services.vram_monitor import VRAMMonitor
    from app.services.lm_studio_client import LMStudioClient
    from app.services.model_manager import ModelManager
    from app.services.model_discovery import ModelDiscoveryService
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from app.services.benchmark_runner import BenchmarkRunner
    from app.services.embedding_service import EmbeddingService
    from app.services.text_chunker import TextChunker
    from app.services.vector_kb import VectorKBService

    state.vram_monitor = VRAMMonitor()
    container.register("vram_monitor", lambda: state.vram_monitor, singleton=True)
    state.lm_client = LMStudioClient(metrics_callback=state.update_metrics)
    container.register("lm_client", lambda: state.lm_client, singleton=True)
    state.model_manager = ModelManager(state.lm_client)
    container.register("model_manager", lambda: state.model_manager, singleton=True)
    state.model_discovery = ModelDiscoveryService(state.lm_client)
    container.register("model_discovery", lambda: state.model_discovery, singleton=True)
    state.pageindex_generator = PageIndexTreeGenerator(state.lm_client)
    container.register("pageindex_generator", lambda: state.pageindex_generator, singleton=True)
    state.benchmark_runner = BenchmarkRunner(state.lm_client, state.vram_monitor, state.model_manager)
    container.register("benchmark_runner", lambda: state.benchmark_runner, singleton=True)
    state.embedding_service = EmbeddingService(state.lm_client, batch_size=32)
    container.register("embedding_service", lambda: state.embedding_service, singleton=True)
    from app.services.deep_research import DeepResearchService

    state.text_chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    container.register("text_chunker", lambda: state.text_chunker, singleton=True)
    state.deep_research_service = DeepResearchService(lm_client=state.lm_client)
    container.register("deep_research_service", lambda: state.deep_research_service, singleton=True)

    _KB_BASE = Path("data/knowledge_bases")
    state.vector_kb_service = VectorKBService(kb_base=_KB_BASE, lm_client=state.lm_client)
    container.register("vector_kb_service", lambda: state.vector_kb_service, singleton=True)

    from app.config import get_settings
    settings = get_settings()

    if settings.memory_enabled:
        from app.services.memory_service import MemoryService
        state.memory_service = MemoryService(db_path=settings.memory_db_path)
        container.register("memory_service", lambda: state.memory_service, singleton=True)
        await state.memory_service.initialize()
        logger.info("Memory service initialized")

    gpu_ok = await state.vram_monitor.initialize()
    logger.info(f"GPU monitor: {'active' if gpu_ok else 'unavailable (no pynvml)'}")

    lm_ok = await state.lm_client.check_health()
    logger.info(f"LM Studio: {'connected' if lm_ok else 'not reachable'}")

    if lm_ok:
        models = await state.lm_client.list_models()
        for m in models:
            mid = m.get("id", m.get("name", "unknown"))
            tier = state.model_manager.get_tier_for_model(mid) or 0
            logger.info(f"Model available: {mid} (tier {tier or 'unknown'})")

    def on_vram(data: dict):
        state._latest_metrics["vram_used_mb"] = data.get("vram_used_mb", 0)
        state._latest_metrics["vram_total_mb"] = data.get("vram_total_mb", 0)
        state._latest_metrics["pressure_level"] = data.get("pressure_level", "green")

    state.vram_monitor.on_update(on_vram)

    await state.benchmark_runner.start_worker()

    vram_task = _lifespan_registry.spawn(state.vram_monitor.start_polling(interval=2.0))
    broadcast_task = _lifespan_registry.spawn(broadcast_loop())
    ttl_task = _lifespan_registry.spawn(ttl_loop())

    for t in (vram_task, broadcast_task, ttl_task):
        state.track_background_task(t)

    state.task_wal = TaskWAL()

    async def _replay_handler(entry: dict) -> None:
        logger.info(
            f"Replaying pending WAL entry: {entry.get('task_name')} "
            f"({entry.get('task_id')})"
        )

    replayed = await state.task_wal.replay_pending(_replay_handler)
    if replayed:
        logger.info(f"Replayed {replayed} pending WAL entries on startup")

    if state.memory_service:
        from app.services.memory_maintenance import memory_maintenance_loop
        maintenance_task = _lifespan_registry.spawn(
            memory_maintenance_loop(state.memory_service, task_wal=state.task_wal)
        )
        state.track_background_task(maintenance_task)

    yield

    if state.memory_service:
        await state.memory_service.close()

    pending = [t for t in list(state.background_tasks) if not t.done()]
    for t in pending:
        t.cancel()
    if pending:
        results = await asyncio.gather(*pending, return_exceptions=True)
        for t, r in zip(pending, results):
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                logger.warning(f"Background task {t.get_name()} raised on shutdown: {r}")
    await _lifespan_registry.cancel_all(timeout=5.0)
    await _global_registry.cancel_all(timeout=5.0)
    logger.info("Shutdown complete.")
