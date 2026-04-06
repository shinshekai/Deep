from functools import cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_host: str = ""
    llm_port: int = 1234
    llm_api_key: str = "lm-studio"
    llm_model: str = ""
    embedding_host: str = ""
    embedding_api_key: str = "lm-studio"
    embedding_model: str = ""
    backend_port: int = 8001
    frontend_port: int = 3782
    turboquant_enabled: bool = True
    turboquant_bits: int = 4
    turboquant_residual_window: int = 256
    turboquant_tier: str = "auto"
    vram_safety_margin_pct: int = 15
    metrics_interval: float = 2.0
    t2_ttl: int = 600
    t3_ttl: int = 300

    class Config:
        env_prefix = ""
        env_file = ".env"


@cache
def get_settings() -> Settings:
    return Settings()
