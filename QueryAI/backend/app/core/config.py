"""
QueryAI Backend — Core Configuration
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "QueryAI"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me"

    # ── Database — App Metadata ────────────────────────────────────────────────
    app_database_url: str = "sqlite:///./storage/queryai_meta.db"

    # ── Database — Business / Analytics ────────────────────────────────────────
    business_database_url: str = "mysql+pymysql://root:rootpassword123@localhost:3306/ai_assistant_demo"
    business_db_schema: str = "public"

    # ── Ollama ─────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_collection: str = "queryai_schema"

    # ── Security ──────────────────────────────────────────────────────────────
    sql_query_timeout: int = 30
    sql_max_rows: int = 1000
    sql_max_retries: int = 2
    rate_limit_per_minute: int = 60

    # ── Backend ────────────────────────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8080
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
