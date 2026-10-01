"""
PolicyPilot — LLM Service Abstraction
Provides clean abstraction for Google Gemini API integration.
LangGraph and agent nodes interact through this service rather than
direct provider dependencies.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


def get_gemini_api_key() -> str:
    """Retrieve the Gemini API key from settings or environment."""
    key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        logger.error("gemini_api_key_missing", message="GEMINI_API_KEY is not set.")
        raise ValueError(
            "GEMINI_API_KEY environment variable is required. "
            "Please configure GEMINI_API_KEY in your .env file."
        )
    return key


class PolicyPilotGeminiChat(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI wrapper ensuring response.content is always str."""

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
        return msg

    def invoke(self, *args, **kwargs):
        res = super().invoke(*args, **kwargs)
        return self._normalize_content(res)

    def _generate(self, *args, **kwargs):
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
    Return a configured Google Gemini Chat Model instance.
    
    Args:
        model: Model name override (defaults to settings.gemini_model)
        temperature: Sampling temperature (0.0 for deterministic RAG)
        json_mode: If True, configure model for structured JSON output
    """
    api_key = get_gemini_api_key()
    model_name = model or settings.gemini_model

    kwargs = {
        "model": model_name,
        "google_api_key": api_key,
        "temperature": temperature,
        "convert_system_message_to_human": False,
    }

    if json_mode:
        kwargs["response_mime_type"] = "application/json"

    logger.debug("init_gemini_llm", model=model_name, temperature=temperature, json_mode=json_mode)
    return PolicyPilotGeminiChat(**kwargs)


@lru_cache(maxsize=1)
def get_embedding_model(model: Optional[str] = None) -> GoogleGenerativeAIEmbeddings:
    """
    Return a cached Google Generative AI Embeddings instance.
    """
    api_key = get_gemini_api_key()
    model_name = model or settings.gemini_embedding_model

    logger.info("init_gemini_embeddings", model=model_name)
    return GoogleGenerativeAIEmbeddings(
        model=model_name,
        google_api_key=api_key,
    )
