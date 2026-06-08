"""Shared application state — avoids circular imports between main.py and routers."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global service instances (populated by main.py lifespan)
vram_monitor = None
lm_client = None
model_manager = None
model_discovery = None
pageindex_generator = None
benchmark_runner = None
embedding_service = None
text_chunker = None
vector_kb_service = None
deep_research_service = None
memory_service = None

# Startup time (set by main.py lifespan)
_startup_time: float = 0.0

# Background tasks spawned during the app's lifetime (vram poller,
# broadcast loop, ttl loop, deep research tasks). The lifespan
# shutdown handler awaits these so a slow task doesn't block exit.
background_tasks: set = set()

# Metrics state
_latest_metrics: dict[str, Any] = {
    "vram_used_mb": 0,
    "vram_total_mb": 0,
    "pressure_level": "green",
    "active_models": [],
    "queue_depths": {"retrieval": 0, "reasoning": 0, "generation": 0},
    "latency_ms": 0,
    "throughput_tps": 0,
    "memory_episodes": 0,
    "memory_facts": 0,
}

_metrics_ws: set = set()


def update_metrics(data: dict):
    """Update global metrics from callbacks."""
    if isinstance(data, dict):
        _latest_metrics.update(data)


def get_metrics() -> dict:
    """Get current metrics snapshot."""
    return dict(_latest_metrics)


def add_ws(ws):
    """Add a WebSocket connection."""
    _metrics_ws.add(ws)


def remove_ws(ws):
    """Remove a WebSocket connection."""
    _metrics_ws.discard(ws)


def get_ws_set():
    """Get the set of active WebSocket connections."""
    return _metrics_ws


def track_background_task(task) -> None:
    """Register a background ``asyncio.Task`` so the lifespan shutdown
    handler can cancel and await it. Idempotent: registering the same
    task twice is a no-op.
    """
    if task in background_tasks:
        return
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
