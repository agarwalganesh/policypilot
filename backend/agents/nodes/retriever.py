"""
PolicyPilot — Retriever Node
Calls the RAG retriever using the analyzed/refined query.
"""
from __future__ import annotations

from typing import Any, Dict

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings
from backend.rag import retriever

logger = get_logger(__name__)
settings = get_settings()


def retriever_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Retrieve relevant policy chunks from ChromaDB.
    Uses refined_query (from query_analyzer) for better retrieval.
    Applies user role for RBAC and temporal_scope for version filtering.
    """
    query = state.get("retrieval_query") or state["query"]
    user_role = state.get("user_role", "employee")
    temporal_scope = state.get("temporal_scope", "current")
    category = state.get("category")

    # Determine status filter based on temporal scope
    status_filter = "active" if temporal_scope == "current" else None

    logger.info(
        "node_retriever",
        query_len=len(query),
        user_role=user_role,
        temporal_scope=temporal_scope,
        category=category,
    )

    docs = retriever.retrieve(
        query=query,
        user_role=user_role,
        top_k=settings.retrieval_top_k,
        status_filter=status_filter,
        category_filter=category,
    )

    logger.info("retriever_node_complete", chunks_retrieved=len(docs))
    return {"retrieved_documents": docs}
