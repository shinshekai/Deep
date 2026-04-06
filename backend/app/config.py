from functools import cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_host: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_host: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    backend_port: int = 8001
    frontend_port: int = 3782
    turboquant_enabled: bool = True
    turboquant_bits: int = 4
    turboquant_tier: str = "auto"
    vram_safety_margin_pct: int = 15
    metrics_interval: float = 2.0

    class Config:
        env_prefix = ""
        env_file = ".env"


@cache
def get_settings() -> Settings:
    return Settings()
