from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Database
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "ai_readonly"
    mysql_password: str = "readonly_password123"
    mysql_database: str = "ai_assistant_demo"
    mysql_admin_user: str = "root"
    mysql_admin_password: str = "rootpassword123"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chroma_collection_name: str = "documents"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8080
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Storage
    storage_path: str = "./storage"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,docx,txt,csv,md,json"

    # Security
    secret_key: str = "change-this-in-production"
    sql_query_timeout: int = 30
    sql_row_limit: int = 1000
    sql_result_size_limit_mb: int = 10

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_retrieval: int = 5

    # MCP
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8090

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",")]

    @property
    def mysql_readonly_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def mysql_admin_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_admin_user}:{self.mysql_admin_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
