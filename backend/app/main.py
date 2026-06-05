"""UDIP Backend — FastAPI application entry point.

Services: VRAMMonitor, LMStudioClient, ModelManager, EmbeddingService,
          TextChunker, VectorKBService
Routers: knowledge, system, agent, retrieval, query, validation
WebSockets: /api/v1/solve (Smart Solve dual-loop), /ws/metrics (broadcast)
"""

import logging
import os
from fastapi import FastAPI

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

from app.config import get_settings
from app.services.logging_config import configure_logging
from app.lifespan import lifespan
from app.websocket_handlers import ws_solve, ws_metrics

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
from app.middleware.rate_limit import register_rate_limiting
from app.middleware.cors import register_cors
from app.middleware.correlation import register_correlation_id
from app.middleware.headers import register_security_headers
from app.middleware.auth import register_auth
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
from app.routers.knowledge import router as knowledge_router
from app.routers.system import router as system_router
from app.routers.agent import router as agent_router
from app.routers.retrieval import router as retrieval_router
from app.routers.query import router as query_router
from app.validation.validation_routes import router as validation_router
from app.routers.memory import router as memory_router

app.include_router(knowledge_router)
app.include_router(system_router)
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
