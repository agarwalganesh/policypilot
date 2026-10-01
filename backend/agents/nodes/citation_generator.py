"""
PolicyPilot — Citation Generator Node
Builds structured, page-accurate citations from retrieved documents.
Every factual answer MUST include citations.
"""
from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document

from backend.agents.state import AgentState
from backend.config import get_logger

logger = get_logger(__name__)


def _deduplicate_sources(sources: List[Dict]) -> List[Dict]:
    """Deduplicate sources by (document_name, page)."""
    seen = set()
    unique = []
    for s in sources:
        key = (s.get("document_name", ""), s.get("page", ""))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def citation_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Extract structured citations from retrieved documents.
    Appends formatted source list to the answer.
    """
    docs = state.get("retrieved_documents", [])
    answer = state.get("answer", "")

    logger.info("node_citation_generator", chunks=len(docs))

    sources = []
    for doc in docs:
        meta = doc.metadata
        source = {
            "document_name": meta.get("document_name", "Unknown Document"),
            "source_file": meta.get("source_file", ""),
            "version": meta.get("version"),
            "effective_date": str(meta.get("effective_date", "")) if meta.get("effective_date") else None,
            "page": meta.get("page"),
            "section": meta.get("section"),
            "chunk_id": meta.get("chunk_id"),
            "relevant_text": doc.page_content[:300],
        }
        sources.append(source)

    sources = _deduplicate_sources(sources)

    # Append citation block to answer
    if sources and answer:
        citation_lines = ["\n\n---\n**Sources:**"]
        for i, s in enumerate(sources, 1):
            line = f"{i}. 📄 **{s['document_name']}**"
            if s.get("page"):
                line += f" — Page {s['page']}"
            if s.get("section"):
                line += f" (§ {s['section']})"
            if s.get("version"):
                line += f" [v{s['version']}]"
            citation_lines.append(line)
        answer = answer + "\n".join(citation_lines)

    logger.info("citations_generated", source_count=len(sources))
    return {
        "answer": answer,
        "sources": sources,
        "decision": "ANSWER",
        "final_confidence": state.get("evidence_confidence", 0.8),
    }
