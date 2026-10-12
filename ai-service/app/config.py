from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://app:change-me-locally@localhost:5432/docassistant"
    internal_api_key: str = ""

    embedding_backend: Literal["fake", "sentence-transformers"] = "sentence-transformers"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384

    llm_backend: Literal["fake", "ollama"] = "fake"
    llm_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 120.0

    # Drop running headers/footers before chunking. Switchable so phase 3 can measure its effect.
    strip_page_boilerplate: bool = True
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 5
    # Tuned against the eval set in phase 3; 0 disables the "no support" refusal.
    min_score: float = 0.0
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
