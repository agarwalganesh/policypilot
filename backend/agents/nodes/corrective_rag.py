"""
PolicyPilot — Corrective RAG Node
Called when initial retrieval is insufficient.
Applies query refinement and re-retrieves.
"""
from __future__ import annotations

from typing import Any, Dict

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings
from backend.rag.corrective_rag import corrective_retrieve

logger = get_logger(__name__)
settings = get_settings()


def corrective_rag_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Apply corrective RAG when evidence is insufficient.
    Increments retry_count and uses refined queries.
    """
    retry_count = state.get("retry_count", 0) + 1
    user_role = state.get("user_role", "employee")
    query = state["query"]

    logger.info("node_corrective_rag", attempt=retry_count)

    new_docs = corrective_retrieve(
        original_query=query,
        user_role=user_role,
        attempt=retry_count,
    )

    # Prioritize newly retrieved docs from corrective RAG, then append existing docs
    existing_docs = state.get("retrieved_documents", [])
    # Docs without a chunk_id can't be deduplicated, so they are always kept
    seen_ids = {
        d.metadata.get("chunk_id")
        for d in new_docs
        if d.metadata and d.metadata.get("chunk_id")
    }
    merged = list(new_docs)
    for doc in existing_docs:
        cid = doc.metadata.get("chunk_id") if doc.metadata else None
        if cid is None or cid not in seen_ids:
            merged.append(doc)
            if cid is not None:
                seen_ids.add(cid)

    # Use combined, de-duplicated documents for next validation pass
    combined = merged[: settings.retrieval_top_k]

    return {
        "retrieved_documents": combined,
        "retry_count": retry_count,
        "retrieval_query": query,  # will be re-validated with new docs
    }
