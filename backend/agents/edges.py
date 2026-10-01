"""
PolicyPilot — LangGraph Edge Conditions
Conditional routing logic between agent nodes.
"""
from __future__ import annotations

from typing import Literal

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


def route_after_access_check(
    state: AgentState,
) -> Literal["retriever", "refusal"]:
    """After access_checker: proceed to retrieval or refuse immediately."""
    if state.get("access_denied"):
        return "refusal"
    return "retriever"


def route_after_query_analysis(
    state: AgentState,
) -> Literal["access_checker", "refusal"]:
    """After query_analyzer: refuse if no policy evidence needed."""
    if not state.get("requires_policy_evidence", True):
        return "refusal"
    return "access_checker"


def route_after_evidence_validation(
    state: AgentState,
) -> Literal["answer_generator", "corrective_rag", "refusal"]:
    """
    After evidence_validator:
    - ANSWER: proceed to answer generation
    - RETRIEVE_AGAIN + retries remaining: corrective RAG
    - RETRIEVE_AGAIN + exhausted: refusal
    """
    if state.get("evidence_sufficient"):
        return "answer_generator"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.max_retries)

    if retry_count < max_retries:
        logger.info(
            "routing_to_corrective_rag",
            retry_count=retry_count,
            max_retries=max_retries,
        )
        return "corrective_rag"

    logger.info("routing_to_refusal", retry_count=retry_count)
    return "refusal"


def route_after_answer_validation(
    state: AgentState,
) -> Literal["citation_generator", "refusal"]:
    """
    After answer_validator:
    - Valid answer: generate citations
    - Invalid: refuse (hallucination detected)
    """
    if state.get("answer_valid", True):
        return "citation_generator"
    logger.warning("answer_failed_validation_routing_to_refusal")
    return "refusal"
