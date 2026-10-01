"""
PolicyPilot — ChromaDB Vector Store
Persistent ChromaDB with metadata filtering for RBAC and version control.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.config import get_logger, get_settings
from backend.rag.embeddings import get_embedding_model

logger = get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def get_chroma_client():
    """Return a cached ChromaDB HTTP client, or fallback to local PersistentClient."""
    try:
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        client.heartbeat()
        logger.info("chromadb_client_init", host=settings.chroma_host, port=settings.chroma_port)
        return client
    except Exception as exc:
        import os
        chroma_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")
        os.makedirs(chroma_dir, exist_ok=True)
        logger.warning(f"ChromaDB HTTP connection failed ({exc}). Using local PersistentClient at {chroma_dir}")
        return chromadb.PersistentClient(path=chroma_dir, settings=ChromaSettings(anonymized_telemetry=False))


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """Return a cached LangChain Chroma vector store."""
    client = get_chroma_client()
    embedding_fn = get_embedding_model()
    store = Chroma(
        client=client,
        collection_name=settings.chroma_collection,
        embedding_function=embedding_fn,
    )
    logger.info("vectorstore_ready", collection=settings.chroma_collection)
    return store


def add_documents(docs: List[Document]) -> List[str]:
    """
    Add chunked documents to ChromaDB.
    Returns list of assigned IDs.
    """
    store = get_vector_store()
    ids = [doc.metadata.get("chunk_id", f"chunk-{i}") for i, doc in enumerate(docs)]
    store.add_documents(documents=docs, ids=ids)
    logger.info("documents_added_to_vectorstore", count=len(docs))
    return ids


def similarity_search(
    query: str,
    top_k: int = None,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Document]:
    """
    Semantic similarity search with optional metadata filtering.
    filter_metadata uses ChromaDB's where clause syntax.
    """
    k = top_k or settings.retrieval_top_k
    store = get_vector_store()

    try:
        if filter_metadata:
            results = store.similarity_search(query, k=k, filter=filter_metadata)
        else:
            results = store.similarity_search(query, k=k)
        logger.info("similarity_search_complete", query_len=len(query), results=len(results))
        return results
    except Exception as exc:
        logger.error("similarity_search_failed", error=str(exc))
        return []


def similarity_search_with_scores(
    query: str,
    top_k: int = None,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[tuple[Document, float]]:
    """
    Search with relevance scores (distance-based — lower = more similar).
    """
    k = top_k or settings.retrieval_top_k
    store = get_vector_store()

    try:
        if filter_metadata:
            results = store.similarity_search_with_score(query, k=k, filter=filter_metadata)
        else:
            results = store.similarity_search_with_score(query, k=k)
        return results
    except Exception as exc:
        logger.error("similarity_search_with_scores_failed", error=str(exc))
        return []


def delete_by_source_file(source_file: str) -> None:
    """Delete all chunks belonging to a specific source file (for re-indexing)."""
    client = get_chroma_client()
    collection = client.get_collection(settings.chroma_collection)
    collection.delete(where={"source_file": {"$eq": source_file}})
    logger.info("chunks_deleted", source_file=source_file)


def collection_stats() -> Dict[str, Any]:
    """Return basic stats about the vector store collection."""
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(settings.chroma_collection)
        count = collection.count()
        return {"collection": settings.chroma_collection, "total_chunks": count}
    except Exception as exc:
        logger.error("collection_stats_failed", error=str(exc))
        return {"collection": settings.chroma_collection, "total_chunks": -1, "error": str(exc)}


def health_check() -> bool:
    """Verify ChromaDB is reachable."""
    try:
        client = get_chroma_client()
        client.heartbeat()
        return True
    except Exception as exc:
        logger.error("chromadb_health_check_failed", error=str(exc))
        return False
