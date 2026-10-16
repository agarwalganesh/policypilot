"""
PolicyPilot — LLM & Embedding Service Abstraction
Provides clean abstraction for Groq API integration (via ChatGroq)
and local high-speed ONNX embeddings (via all-MiniLM-L6-v2).
LangGraph and agent nodes interact through this service.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache
from typing import List, Optional

import httpx
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


def get_groq_api_key() -> str:
    """Retrieve the Groq API key from settings or environment."""
    key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
    if not key:
        logger.error("groq_api_key_missing", message="GROQ_API_KEY is not set.")
        raise ValueError(
            "GROQ_API_KEY environment variable is required. "
            "Please configure GROQ_API_KEY in your .env file."
        )
    return key


# Backward compatibility alias
get_gemini_api_key = get_groq_api_key


class PolicyPilotGroqChat(ChatGroq):
    """ChatGroq wrapper ensuring response.content is always str."""

    def _normalize_content(self, msg):
        if hasattr(msg, "content") and isinstance(msg.content, list):
            parts = []
            for p in msg.content:
                if isinstance(p, dict) and "text" in p:
                    parts.append(p["text"])
                elif isinstance(p, str):
                    parts.append(p)
                else:
                    parts.append(str(p))
            msg.content = "".join(parts)
        elif hasattr(msg, "content") and not isinstance(msg.content, str):
            msg.content = str(msg.content)
        return msg

    def invoke(self, *args, **kwargs):
        res = super().invoke(*args, **kwargs)
        return self._normalize_content(res)

    def _generate(self, *args, **kwargs):
        # Covers batch/ainvoke paths that bypass invoke()
        chat_result = super()._generate(*args, **kwargs)
        for gen in chat_result.generations:
            self._normalize_content(gen.message)
        return chat_result


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.0,
    json_mode: bool = False,
) -> BaseChatModel:
    """
    Return a configured Groq Chat Model instance.
    
    Args:
        model: Model name override (defaults to settings.groq_model)
        temperature: Sampling temperature (0.0 for deterministic RAG)
        json_mode: If True, configure model for structured JSON output
    """
    api_key = get_groq_api_key()
    model_name = model or settings.groq_model

    kwargs = {
        "model": model_name,
        "groq_api_key": api_key,
        "temperature": temperature,
    }

    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

    logger.debug("init_groq_llm", model=model_name, temperature=temperature, json_mode=json_mode)
    return PolicyPilotGroqChat(**kwargs)


class LocalChromaEmbeddings(Embeddings):
    """
    Zero-external-dependency local embedding model using ONNX-based all-MiniLM-L6-v2.
    Groq does not provide an embedding endpoint, so local embedding ensures
    ultra-fast, private, quota-free vector search.
    """

    def __init__(self):
        self._ef = DefaultEmbeddingFunction()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        res = self._ef(texts)
        return [e.tolist() if hasattr(e, "tolist") else list(e) for e in res]

    def embed_query(self, text: str) -> List[float]:
        res = self._ef([text])
        item = res[0]
        return item.tolist() if hasattr(item, "tolist") else list(item)


class HuggingFaceHostedEmbeddings(Embeddings):
    """
    all-MiniLM-L6-v2 via the Hugging Face Inference API.
    Used on serverless hosts (Vercel) where the local ONNX model can't be
    downloaded; produces the same 384-dim vectors as LocalChromaEmbeddings.
    """

    _BATCH_SIZE = 32

    def __init__(self, api_token: str, model: str):
        self._url = (
            f"https://router.huggingface.co/hf-inference/models/{model}"
            "/pipeline/feature-extraction"
        )
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._client = httpx.Client(timeout=30.0)

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _embed(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            resp = self._client.post(
                self._url,
                headers=self._headers,
                json={"inputs": batch, "options": {"wait_for_model": True}},
            )
            resp.raise_for_status()
            vectors.extend(self._normalize(v) for v in resp.json())
        return vectors

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]


@lru_cache(maxsize=1)
def get_embedding_model(model: Optional[str] = None) -> Embeddings:
    """
    Return a cached embedding instance for the configured provider.
    """
    provider = settings.embedding_provider.lower()
    if provider == "huggingface":
        token = settings.hf_api_token or os.getenv("HF_API_TOKEN")
        if not token:
            raise ValueError(
                "HF_API_TOKEN is required when EMBEDDING_PROVIDER=huggingface."
            )
        logger.info("init_hf_embeddings", model=settings.hf_embedding_model)
        return HuggingFaceHostedEmbeddings(token, settings.hf_embedding_model)

    # The local ONNX function only ships all-MiniLM-L6-v2
    if "minilm-l6-v2" not in settings.embedding_model.lower():
        raise ValueError(
            f"EMBEDDING_MODEL={settings.embedding_model} is not supported locally; "
            "only all-MiniLM-L6-v2 is available with EMBEDDING_PROVIDER=local."
        )
    logger.info("init_local_embeddings", model=settings.embedding_model)
    return LocalChromaEmbeddings()
