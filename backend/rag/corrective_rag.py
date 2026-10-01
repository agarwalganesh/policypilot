"""
PolicyPilot — Corrective RAG
Query refinement strategies when initial retrieval is insufficient.
"""
from __future__ import annotations

import re
from typing import List, Optional

from langchain_core.documents import Document

from backend.config import get_logger, get_settings
from backend.rag import retriever

logger = get_logger(__name__)
settings = get_settings()

# Policy keyword synonyms for query expansion
POLICY_SYNONYMS = {
    "leave": ["leave policy", "casual leave", "sick leave", "annual leave", "pl", "cl", "sl"],
    "salary": ["compensation", "pay", "ctc", "fixed pay", "variable pay"],
    "separation": ["exit", "resignation", "termination", "notice period", "fnf", "full and final"],
    "travel": ["travel reimbursement", "business travel", "international travel", "hotel", "meal"],
    "attendance": ["shift", "working hours", "wfh", "work from home", "remote"],
    "probation": ["confirmation", "probationary period", "trial period"],
    "insurance": ["medical coverage", "group medical", "health insurance", "gtli"],
    "performance": ["pip", "performance improvement", "kpi", "appraisal"],
    "gift": ["gifts policy", "no gifts", "wedding gift"],
    "conduct": ["code of conduct", "code of business", "behavior", "ethics"],
    "ai": ["ai sop", "artificial intelligence", "vibe coding", "ai tools", "copilot"],
    "reimbursement": ["expense", "claim", "reimburse", "internet reimbursement"],
    "conflict": ["conflict of interest", "dual employment"],
    "corruption": ["anti-corruption", "bribery", "aml"],
}


def refine_query(original_query: str) -> List[str]:
    """
    Generate a list of refined query variants.
    Returns ordered list: original → keyword-extracted → synonym-expanded.
    """
    refined = []

    # Strategy 1: Remove filler words
    filler_pattern = re.compile(
        r"\b(what|how|does|do|is|are|can|i|the|a|an|me|my|please|tell|explain|about|regarding|for|at|of|to|in|on)\b",
        re.IGNORECASE,
    )
    stripped = filler_pattern.sub("", original_query).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if stripped and stripped.lower() != original_query.lower():
        refined.append(stripped)

    # Strategy 2: Extract policy-specific keywords
    query_lower = original_query.lower()
    for concept, synonyms in POLICY_SYNONYMS.items():
        if concept in query_lower or any(s in query_lower for s in synonyms):
            keyword_query = f"policy {concept} {' '.join(synonyms[:3])}"
            refined.append(keyword_query)

    # Strategy 3: Add "PW policy" prefix for context
    refined.append(f"Physics Wallah policy {original_query}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in refined:
        if q.lower() not in seen and q.strip():
            seen.add(q.lower())
            unique.append(q)

    return unique[:3]  # Return at most 3 refined variants


def corrective_retrieve(
    original_query: str,
    user_role: str = "employee",
    attempt: int = 1,
) -> List[Document]:
    """
    Execute corrective retrieval using refined queries.
    Combines results from multiple query variants for broader coverage.

    Args:
        original_query: The user's original question
        user_role: For RBAC filtering
        attempt: Current retry attempt number

    Returns:
        List of documents from best refined query
    """
    logger.info("corrective_rag_triggered", attempt=attempt, query_len=len(original_query))

    refined_queries = refine_query(original_query)
    logger.info("corrective_queries_generated", count=len(refined_queries))

    best_results: List[Document] = []
    seen_chunk_ids = set()

    for idx, query in enumerate(refined_queries):
        results = retriever.retrieve(
            query=query,
            user_role=user_role,
            top_k=settings.retrieval_top_k,
        )
        # Deduplicate by chunk_id
        for doc in results:
            cid = doc.metadata.get("chunk_id", "")
            if cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                best_results.append(doc)

        logger.info(
            "corrective_query_result",
            attempt=attempt,
            query_variant=idx + 1,
            results=len(results),
        )

    logger.info(
        "corrective_rag_complete",
        attempt=attempt,
        total_unique_chunks=len(best_results),
    )
    return best_results[:settings.retrieval_top_k]
