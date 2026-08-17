"""
Central configuration, loaded from environment variables / .env.
Nothing here talks to a model — this whole service is the deterministic
verification path from the BRD (FR-3.1-3.4): no LLM anywhere in this flow.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./verification.db"
    name_match_threshold: float = 0.82
    request_timeout_seconds: int = 10


settings = Settings()
