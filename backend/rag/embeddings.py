"""
PolicyPilot — Embeddings
Wraps Google Gemini embeddings via the centralized LLM service
with retry logic and health check.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import get_logger, get_settings
from backend.services.llm import get_embedding_model as get_gemini_embedding_model

logger = get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def get_embedding_model():
    """Return a cached embedding model instance."""
    logger.info(
        "embedding_model_init",
        model=settings.gemini_embedding_model,
    )
    return get_gemini_embedding_model(model=settings.gemini_embedding_model)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts with retry on transient failures."""
    model = get_embedding_model()
    return model.embed_documents(texts)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def embed_query(query: str) -> List[float]:
    """Embed a single query string with retry on transient failures."""
    model = get_embedding_model()
    return model.embed_query(query)


def health_check() -> bool:
    """Verify embedding model is available and functional."""
    try:
        _ = embed_query("health check")
        return True
    except Exception as exc:
        logger.error("embedding_health_check_failed", error=str(exc))
        return False
