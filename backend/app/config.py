"""Application settings, loaded from environment / .env file.

The auth token is auto-generated on first start and persisted to ``.env``
if it isn't already set. This removes the hardcoded default credential
that previously lived in the source tree.
"""

import logging
import os
from functools import cache
from pathlib import Path
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.security import generate_auth_token

logger = logging.getLogger(__name__)

# Where the auto-generated token is stored if not provided via env.
_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / ".auth_token"


def _load_or_create_token() -> str:
    """Resolve the auth token from env, file, or generate a new one."""
    env_token = os.environ.get("WS_AUTH_TOKEN") or os.environ.get("UDIP_AUTH_TOKEN")
    if env_token:
        return env_token

    if _TOKEN_FILE.exists():
        try:
            token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError as e:
            logger.warning(f"Could not read auth token file: {e}")

    # First boot — generate and persist a strong random token.
    token = generate_auth_token(32)
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(token, encoding="utf-8")
        # Restrict permissions on POSIX
        if os.name != "nt":
            os.chmod(_TOKEN_FILE, 0o600)
        logger.info(
            "Generated new auth token and persisted to %s — "
            "set WS_AUTH_TOKEN env var to override.",
            _TOKEN_FILE,
        )
    except OSError as e:
        logger.warning(f"Could not persist auth token: {e}")
    return token


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    llm_host: str = "http://localhost:1234"
    llm_port: int = 1234
    llm_api_key: str = "lm-studio"
    llm_model: str = "Qwen3-1.7B-Q4_K_M"
    embedding_host: str = "http://localhost:1234"
    embedding_api_key: str = "lm-studio"
    embedding_model: str = "text-embedding-qwen3-embedding-8b"
    backend_port: int = 8001
    frontend_port: int = 3782
    # ``ws_auth_token`` is resolved at startup via ``_load_or_create_token``
    # so we always have a strong, non-default value.
    ws_auth_token: str = ""
    turboquant_enabled: bool = True
    turboquant_bits: int = 4
    turboquant_residual_window: int = 256
    turboquant_tier: str = "auto"
    vram_safety_margin_pct: int = 15
    pageindex_model: str = ""
    pageindex_max_pages_per_node: int = 10
    pageindex_max_tokens_per_node: int = 20000
    ocr_backend: str = "pytesseract"
    metrics_interval: float = 2.0
    t2_ttl: int = 600
    t3_ttl: int = 300
    memory_enabled: bool = True
    memory_db_path: str = "data/memory/deep_memory.db"
    memory_max_episodes_recall: int = 5
    memory_max_facts_recall: int = 10
    memory_fact_confidence_threshold: float = 0.2
    memory_decay_rate: float = 0.1
    memory_extraction_model_tier: int = 1
    otel_exporter_otlp_endpoint: Optional[str] = None  # e.g. "http://localhost:4317"
    otel_console_export: bool = False

    def model_post_init(self, __context) -> None:
        # Fill in the auth token if it wasn't provided via env.
        if not self.ws_auth_token:
            self.ws_auth_token = _load_or_create_token()


@cache
def get_settings() -> Settings:
    return Settings()
