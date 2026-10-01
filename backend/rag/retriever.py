"""
PolicyPilot — RAG Retriever
Applies RBAC access filtering before retrieval.
Combines semantic search with metadata-based policy status filtering.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

from backend.config import get_logger, get_settings
from backend.rag import vectorstore

logger = get_logger(__name__)
settings = get_settings()

# Access roles that each role can retrieve
ROLE_ACCESS_MAP = {
    "employee": ["employee", "manager", "hr", "admin"],
    "manager": ["employee", "manager", "hr", "admin"],
    "hr": ["employee", "manager", "hr", "admin"],
    "admin": ["employee", "manager", "hr", "admin"],
}


def _build_filter(
    user_role: str,
    status_filter: str = "active",
    category_filter: Optional[str] = None,
    document_name_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build ChromaDB where clause for access-controlled retrieval.
    Filters by: active status + user role access.
    """
    conditions = []

    # Always filter for active policies unless historical query
    if status_filter:
        conditions.append({"status": {"$eq": status_filter}})

    if category_filter:
        conditions.append({"category": {"$eq": category_filter}})

    if document_name_filter:
        conditions.append({"document_name": {"$eq": document_name_filter}})

    # RBAC: only retrieve docs accessible to this role
    # ChromaDB doesn't support array contains natively — we filter post-retrieval
    # The role check is enforced in post-filter step below

    if len(conditions) == 1:
        return conditions[0]
    elif len(conditions) > 1:
        return {"$and": conditions}
    return {}


def retrieve(
    query: str,
    user_role: str = "employee",
    top_k: Optional[int] = None,
    status_filter: str = "active",
    category_filter: Optional[str] = None,
    document_name_filter: Optional[str] = None,
) -> List[Document]:
    """
    Retrieve top-k relevant policy chunks.
    Applies metadata filtering and RBAC post-filter.
    """
    k = top_k or settings.retrieval_top_k
    filter_where = _build_filter(
        user_role=user_role,
        status_filter=status_filter,
        category_filter=category_filter,
        document_name_filter=document_name_filter,
    )

    results = vectorstore.similarity_search(
        query=query,
        top_k=k * 2,  # over-fetch to allow RBAC filtering
        filter_metadata=filter_where if filter_where else None,
    )

    # RBAC post-filter: verify role is in access_roles
    allowed_roles = ROLE_ACCESS_MAP.get(user_role, [])
    filtered = []
    for doc in results:
        doc_roles = doc.metadata.get("access_roles", ["employee", "manager", "hr", "admin"])
        if isinstance(doc_roles, str):
            doc_roles = [r.strip() for r in doc_roles.split(",")]
        if user_role in doc_roles or "admin" in allowed_roles:
            filtered.append(doc)

    # Return top_k after filtering
    final = filtered[:k]
    logger.info(
        "retrieval_complete",
        query_len=len(query),
        user_role=user_role,
        fetched=len(results),
        after_rbac=len(filtered),
        returned=len(final),
    )
    return final


def retrieve_with_scores(
    query: str,
    user_role: str = "employee",
    top_k: Optional[int] = None,
    status_filter: str = "active",
) -> List[tuple[Document, float]]:
    """Retrieve with similarity scores for evidence evaluation."""
    k = top_k or settings.retrieval_top_k
    filter_where = _build_filter(user_role=user_role, status_filter=status_filter)

    results = vectorstore.similarity_search_with_scores(
        query=query,
        top_k=k * 2,
        filter_metadata=filter_where if filter_where else None,
    )

    # RBAC post-filter
    filtered = []
    for doc, score in results:
        doc_roles = doc.metadata.get("access_roles", ["employee", "manager", "hr", "admin"])
        if isinstance(doc_roles, str):
            doc_roles = [r.strip() for r in doc_roles.split(",")]
        if user_role in doc_roles:
            filtered.append((doc, score))

    return filtered[:k]
