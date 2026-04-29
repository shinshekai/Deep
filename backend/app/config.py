from functools import cache
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="", env_file=".env")

    llm_host: str = ""
    llm_port: int = 1234
    llm_api_key: str = "lm-studio"
    llm_model: str = ""
    embedding_host: str = ""
    embedding_api_key: str = "lm-studio"
    embedding_model: str = "text-embedding-qwen3-embedding-8b"
    backend_port: int = 8001
    frontend_port: int = 3782
    turboquant_enabled: bool = True
    turboquant_bits: int = 4
    turboquant_residual_window: int = 256
    turboquant_tier: str = "auto"
    vram_safety_margin_pct: int = 15
    pageindex_model: str = ""
    pageindex_max_pages_per_node: int = 10
    pageindex_max_tokens_per_node: int = 20000
    metrics_interval: float = 2.0
    t2_ttl: int = 600
    t3_ttl: int = 300


@cache
def get_settings() -> Settings:
    return Settings()
