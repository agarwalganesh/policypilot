"""
PolicyPilot — Application Configuration
All settings are loaded from environment variables (never hardcoded).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    app_name: str = "PolicyPilot"
    app_version: str = "1.0.0"
    flask_env: str = "development"
    flask_secret_key: str = "change-this-to-a-long-random-secret"
    log_level: str = "INFO"

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql://policypilot:policypilot@localhost:5432/policypilot"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "policypilot"
    postgres_password: str = "policypilot"
    postgres_db: str = "policypilot"

    # ── ChromaDB ──────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "policy_documents"
    chroma_persist_dir: Optional[str] = None  # local fallback; defaults to <project>/chroma_db

    # ── Groq (LLM) ────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Embeddings ────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_dimensions: int = 384  # alias used by some modules
    # "huggingface" = hosted Inference API (for Vercel), "local" = ONNX on disk.
    # Both run all-MiniLM-L6-v2, so vectors stay compatible across providers.
    embedding_provider: str = "local"
    hf_api_token: Optional[str] = None
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Backwards-compatibility Aliases ───────────────────────
    @property
    def gemini_api_key(self) -> Optional[str]:
        return self.groq_api_key

    @property
    def gemini_model(self) -> str:
        return self.groq_model

    @property
    def gemini_embedding_model(self) -> str:
        return self.embedding_model

    # ── RAG ───────────────────────────────────────────────────
    retrieval_top_k: int = 5
    evidence_threshold: float = 0.65
    min_similarity: float = 0.4
    max_retries: int = 2
    chunk_size: int = 512
    chunk_overlap: int = 50
    chunking_strategy: str = "recursive"

    # ── Auth ──────────────────────────────────────────────────
    jwt_secret: str = "change-this-to-another-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # ── LangSmith (optional) ──────────────────────────────────
    langsmith_api_key: str = ""
    langsmith_project: str = "policypilot"
    langsmith_tracing: bool = False
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ── CORS ──────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"

    # ── File Upload ───────────────────────────────────────────
    max_upload_size_mb: int = 50
    upload_allowed_extensions: str = "pdf,docx"
    allowed_extensions: str = "pdf,docx,txt"  # alias used by documents route
    documents_raw_dir: str = "documents/raw"
    documents_processed_dir: str = "documents/processed"
    documents_rejected_dir: str = "documents/rejected"

    # ── Admin ─────────────────────────────────────────────────
    admin_email: str = "admin@physicswallah.com"
    admin_password: str = "Admin@123!Change_This"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def allowed_extensions_set(self) -> set:
        return {e.strip().lower() for e in self.upload_allowed_extensions.split(",")}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key)

    def configure_langsmith(self) -> None:
        """Set LangSmith env vars if tracing is enabled."""
        if self.langsmith_enabled:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project
            os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_endpoint


@lru_cache()
def get_settings() -> Settings:
    return Settings()
