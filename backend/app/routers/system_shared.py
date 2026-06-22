"""Shared state for system route modules — extracted from system.py monolith."""

import logging
from pathlib import Path

METRICS_DIR = Path("data/metrics")
METRICS_DIR.mkdir(parents=True, exist_ok=True)
_metrics_history: list = []

_cache_state: dict = {}

_rotation_history: list = []
_ROTATION_HISTORY_MAX = 50

CONFIG_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "llm_model",
        "embedding_model",
        "turboquant_enabled",
        "turboquant_bits",
        "turboquant_residual_window",
        "turboquant_tier",
        "vram_safety_margin_pct",
        "pageindex_model",
        "t2_ttl",
        "t3_ttl",
        "metrics_interval",
        "enable_thinking",
    }
)

URL_FIELDS: frozenset[str] = frozenset({"llm_host", "embedding_host"})

logger = logging.getLogger("system")


def _mask_value(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "*" * (len(value) - 8) + value[-4:]
