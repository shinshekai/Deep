"""UDIP Backend — FastAPI application entry point.

Services: VRAMMonitor, LMStudioClient, ModelManager, EmbeddingService,
          TextChunker, VectorKBService
Routers: knowledge, system, agent, retrieval, query, validation
WebSockets: /api/v1/solve (Smart Solve dual-loop), /ws/metrics (broadcast)
"""

import logging
import os

from fastapi import FastAPI

from app.config import get_settings
from app.services.telemetry import setup_tracing

settings = get_settings()
provider = setup_tracing(
    service_name="udip-backend",
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    console_export=settings.otel_console_export,
)
if provider is not None:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
else:
    tracer = None

from app.lifespan import lifespan
from app.services.logging_config import configure_logging
from app.websocket_handlers import ws_metrics, ws_solve

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

os.makedirs("data/metrics", exist_ok=True)


# ─── App ───

app = FastAPI(
    title="UDIP Backend",
    description="Unified Document Intelligence Pipeline — FastAPI backend",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Middleware (extracted to app/middleware/) ────────────────────────
from app.middleware.auth import register_auth
from app.middleware.correlation import register_correlation_id
from app.middleware.cors import register_cors
from app.middleware.headers import register_security_headers
from app.middleware.rate_limit import register_rate_limiting
from app.services.metrics import MetricsMiddleware

register_rate_limiting(app)
register_cors(app, settings)
app.add_middleware(MetricsMiddleware)
register_correlation_id(app)
register_security_headers(app)
register_auth(app, settings)

if tracer:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


# Import routers after middleware setup
from app.routers.agent import router as agent_router
from app.routers.backup import router as backup_router
from app.routers.benchmarks import router as benchmarks_router
from app.routers.config_routes import router as config_router
from app.routers.data_routes import router as data_router
from app.routers.health import router as health_router
from app.routers.knowledge import router as knowledge_router
from app.routers.memory import router as memory_router
from app.routers.model_routes import router as model_router
from app.routers.query import router as query_router
from app.routers.retrieval import router as retrieval_router
from app.routers.vram import router as vram_router
from app.validation.validation_routes import router as validation_router

app.include_router(health_router)
app.include_router(config_router)
app.include_router(model_router)
app.include_router(vram_router)
app.include_router(benchmarks_router)
app.include_router(data_router)
app.include_router(backup_router)
app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(retrieval_router)
app.include_router(query_router)
app.include_router(validation_router)
app.include_router(memory_router)


# ── Prometheus /metrics endpoint ──────────────────────────────────────
from app.services.metrics import metrics_endpoint

app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)


# ── Re-export for backward compatibility with tests ──
from app.websocket_handlers import _run_solve_pipeline_for_message  # noqa: F401

app.websocket("/api/v1/solve")(ws_solve)
app.websocket("/ws/metrics")(ws_metrics)
