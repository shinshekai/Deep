"""Service container — wraps dependencies.Container with module-level backward compat.

Maintains backward compatibility with `from app import state` imports.
Services registered via `state.container.register()` or `state.<name> = instance`.
Testing overrides via `state.container.override()` with ContextVar safety.
"""

from contextvars import ContextVar
from typing import Any

from app.dependencies import Container as _Container, set_container

# Request-scoped override context
_override_ctx: ContextVar[dict[str, Any] | None] = ContextVar("svc_override_ctx", default=None)


class ServiceContainer(_Container):
    """Extended container with request-scoped overrides and module syncing."""

    def register_svc(self, name: str, service: Any) -> None:
        """Register a service instance and sync to module-level attribute."""
        self.register(name, lambda: service, singleton=True)
        globals()[name] = service

    def resolve(self, name: str) -> Any:
        """Resolve with ContextVar override support."""
        ctx = _override_ctx.get()
        if ctx and name in ctx:
            return ctx[name]
        return self.get(name)

    def scoped_override(self, **overrides: Any) -> "ScopedOverride":
        """Return a ContextVar-safe context manager for test overrides."""
        return ScopedOverride(overrides)

    def list_services(self) -> list[str]:
        return list(self._services.keys())


class ScopedOverride:
    """Async-safe ContextVar override context manager."""

    def __init__(self, overrides: dict[str, Any]):
        self._overrides = overrides
        self._token = None

    def __enter__(self):
        self._token = _override_ctx.set(self._overrides)
        return self

    def __exit__(self, *args):
        _override_ctx.reset(self._token)
        self._token = None


# Singleton container — replaces dependencies.container so both are the same instance
container = ServiceContainer()
set_container(container)

# Module-level service references (backward-compatible, populated by lifespan)
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

# Startup timestamp
_startup_time: float = 0.0

# Background tasks
background_tasks: set = set()

# Metrics
_latest_metrics: dict[str, Any] = {
    "vram_used_mb": 0, "vram_total_mb": 0, "pressure_level": "green",
    "active_models": [], "queue_depths": {}, "latency_ms": 0, "throughput_tps": 0,
    "memory_episodes": 0, "memory_facts": 0,
}
_metrics_ws: set = set()


def update_metrics(data: dict):
    if isinstance(data, dict):
        _latest_metrics.update(data)


def get_metrics() -> dict:
    return dict(_latest_metrics)


def add_ws(ws):
    _metrics_ws.add(ws)


def remove_ws(ws):
    _metrics_ws.discard(ws)


def get_ws_set():
    return _metrics_ws


def track_background_task(task) -> None:
    if task in background_tasks:
        return
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
