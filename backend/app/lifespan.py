"""Application lifespan — extracted from main.py for modularity.

Manages startup/shutdown of services, background tasks, and the
async context manager passed to FastAPI.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app import state
from app.services.task_registry import TaskRegistry, _global_registry
from app.services.task_wal import TaskWAL
from app.websocket_handlers import broadcast_loop, ttl_loop

logger = logging.getLogger(__name__)

_lifespan_registry = TaskRegistry(name="lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    state._startup_time = time.time()
    logger.info("Starting UDIP Backend on :8001")

    from app.services.benchmark_runner import BenchmarkRunner
    from app.services.embedding_service import EmbeddingService
    from app.services.lm_studio_client import LMStudioClient
    from app.services.model_discovery import ModelDiscoveryService
    from app.services.model_manager import ModelManager
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from app.services.text_chunker import TextChunker
    from app.services.vector_kb import VectorKBService
    from app.services.vram_monitor import VRAMMonitor

    state.vram_monitor = VRAMMonitor()
    state.container.register_svc("vram_monitor", state.vram_monitor)
    state.lm_client = LMStudioClient(metrics_callback=state.update_metrics)
    state.container.register_svc("lm_client", state.lm_client)
    state.model_manager = ModelManager(state.lm_client)
    state.container.register_svc("model_manager", state.model_manager)
    state.model_discovery = ModelDiscoveryService(state.lm_client)
    state.container.register_svc("model_discovery", state.model_discovery)
    state.pageindex_generator = PageIndexTreeGenerator(state.lm_client)
    state.container.register_svc("pageindex_generator", state.pageindex_generator)
    state.benchmark_runner = BenchmarkRunner(
        state.lm_client, state.vram_monitor, state.model_manager
    )
    state.container.register_svc("benchmark_runner", state.benchmark_runner)
    state.embedding_service = EmbeddingService(state.lm_client, batch_size=32)
    state.container.register_svc("embedding_service", state.embedding_service)
    from app.services.deep_research import DeepResearchService

    state.text_chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    state.container.register_svc("text_chunker", state.text_chunker)
    state.deep_research_service = DeepResearchService(lm_client=state.lm_client)
    state.container.register_svc("deep_research_service", state.deep_research_service)

    _KB_BASE = Path("data/knowledge_bases")
    state.vector_kb_service = VectorKBService(kb_base=_KB_BASE, lm_client=state.lm_client)
    state.container.register_svc("vector_kb_service", state.vector_kb_service)

    from app.config import get_settings

    settings = get_settings()

    if settings.memory_enabled:
        from app.services.memory_service import MemoryService

        state.memory_service = MemoryService(db_path=settings.memory_db_path)
        state.container.register_svc("memory_service", state.memory_service)
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

    vram_task = _lifespan_registry.spawn(state.vram_monitor.start_polling())
    broadcast_task = _lifespan_registry.spawn(broadcast_loop())
    ttl_task = _lifespan_registry.spawn(ttl_loop())

    for t in (vram_task, broadcast_task, ttl_task):
        state.track_background_task(t)

    state.task_wal = TaskWAL()

    async def _replay_handler(entry: dict) -> None:
        logger.info(
            f"Replaying pending WAL entry: {entry.get('task_name')} ({entry.get('task_id')})"
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
        for t, r in zip(pending, results, strict=False):
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                logger.warning(f"Background task {t.get_name()} raised on shutdown: {r}")
    await _lifespan_registry.cancel_all(timeout=5.0)
    await _global_registry.cancel_all(timeout=5.0)
    logger.info("Shutdown complete.")
