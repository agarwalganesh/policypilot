"""
PolicyPilot — LangGraph Agent Graph
Orchestrates the full agentic RAG pipeline.

Flow:
  START
    ↓
  query_analyzer
    ↓
  access_checker
    ↓
  retriever
    ↓
  evidence_validator
    ↓ (conditional)
    ├── [SUFFICIENT] → answer_generator → answer_validator → citation_generator → END
    └── [INSUFFICIENT]
          ├── [retries left] → corrective_rag → retriever → evidence_validator
          └── [max retries] → refusal → END
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from langgraph.graph import END, START, StateGraph

from backend.agents.edges import (
    route_after_access_check,
    route_after_answer_validation,
    route_after_evidence_validation,
    route_after_query_analysis,
)
from backend.agents.nodes.access_checker import access_checker_node
from backend.agents.nodes.answer_generator import answer_generator_node
from backend.agents.nodes.answer_validator import answer_validator_node
from backend.agents.nodes.citation_generator import citation_generator_node
from backend.agents.nodes.corrective_rag import corrective_rag_node
from backend.agents.nodes.evidence_validator import evidence_validator_node
from backend.agents.nodes.query_analyzer import query_analyzer_node
from backend.agents.nodes.refusal import refusal_node
from backend.agents.nodes.retriever import retriever_node
from backend.agents.state import AgentState
from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


def _build_graph() -> StateGraph:
    """Build and compile the LangGraph state graph."""
    graph = StateGraph(AgentState)

    # ── Register Nodes ────────────────────────────────────────
    graph.add_node("query_analyzer", query_analyzer_node)
    graph.add_node("access_checker", access_checker_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("evidence_validator", evidence_validator_node)
    graph.add_node("corrective_rag", corrective_rag_node)
    graph.add_node("answer_generator", answer_generator_node)
    graph.add_node("answer_validator", answer_validator_node)
    graph.add_node("citation_generator", citation_generator_node)
    graph.add_node("refusal", refusal_node)

    # ── Entry Point ───────────────────────────────────────────
    graph.add_edge(START, "query_analyzer")

    # ── Conditional: after query analysis ─────────────────────
    graph.add_conditional_edges(
        "query_analyzer",
        route_after_query_analysis,
        {"access_checker": "access_checker", "refusal": "refusal"},
    )

    # ── Conditional: after access check ───────────────────────
    graph.add_conditional_edges(
        "access_checker",
        route_after_access_check,
        {"retriever": "retriever", "refusal": "refusal"},
    )

    # ── Retriever → Evidence Validator ────────────────────────
    graph.add_edge("retriever", "evidence_validator")

    # ── Conditional: after evidence validation ────────────────
    graph.add_conditional_edges(
        "evidence_validator",
        route_after_evidence_validation,
        {
            "answer_generator": "answer_generator",
            "corrective_rag": "corrective_rag",
            "refusal": "refusal",
        },
    )

    # ── Corrective RAG loop ───────────────────────────────────
    graph.add_edge("corrective_rag", "evidence_validator")

    # ── Answer path ───────────────────────────────────────────
    graph.add_edge("answer_generator", "answer_validator")
    graph.add_conditional_edges(
        "answer_validator",
        route_after_answer_validation,
        {"citation_generator": "citation_generator", "refusal": "refusal"},
    )
    graph.add_edge("citation_generator", END)

    # ── Refusal terminal ──────────────────────────────────────
    graph.add_edge("refusal", END)

    return graph


# Compile the graph once at module load
_compiled_graph = _build_graph().compile()


def run_agent(
    query: str,
    user_id: str = "anonymous",
    user_role: str = "employee",
    conversation_id: Optional[str] = None,
    conversation_history: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Execute the full LangGraph pipeline for a user query.

    Args:
        query: The user's question
        user_id: Authenticated user ID
        user_role: User's role for RBAC
        conversation_id: Existing conversation ID (for context)
        conversation_history: List of {role, content} dicts

    Returns:
        Final AgentState as dict with answer, sources, decision, confidence
    """
    query_id = str(uuid.uuid4())
    start_time = time.time()

    # Configure LangSmith tracing if enabled
    if settings.langsmith_enabled:
        settings.configure_langsmith()

    initial_state: AgentState = {
        # Identity
        "user_id": user_id,
        "user_role": user_role,
        "conversation_id": conversation_id,
        "query_id": query_id,
        # Query
        "query": query.strip(),
        "conversation_history": conversation_history or [],
        # Analysis (populated by query_analyzer)
        "intent": None,
        "category": None,
        "temporal_scope": "current",
        "requires_policy_evidence": True,
        "refined_query": None,
        # Access
        "access_scope": [],
        "access_denied": False,
        # Retrieval
        "retrieved_documents": [],
        "retrieval_query": query.strip(),
        # Evidence
        "evidence_sufficient": False,
        "evidence_confidence": 0.0,
        "evidence_reason": "",
        "evidence_summary": "",
        # Retry
        "retry_count": 0,
        "max_retries": settings.max_retries,
        # Answer
        "answer": None,
        "raw_answer": None,
        "answer_valid": False,
        "answer_validation_reason": "",
        # Citations
        "sources": [],
        # Decision
        "decision": "REFUSE",
        "final_confidence": 0.0,
        # Observability
        "agent_trace_id": query_id,
        "start_time": start_time,
        "latency_ms": 0,
        "error": None,
    }

    try:
        logger.info(
            "agent_run_start",
            query_id=query_id,
            user_id=user_id,
            user_role=user_role,
            query_len=len(query),
        )

        final_state = _compiled_graph.invoke(initial_state)

        end_time = time.time()
        # Structured Diagnostic Output
        retrieved_docs = final_state.get("retrieved_documents", [])
        debug_log = [
            "\n" + "=" * 50,
            "RAG DIAGNOSTIC TRACE",
            "=" * 50,
            f"QUERY:\n{query}",
            "\nQUERY ANALYSIS:",
            f"  intent:          {final_state.get('intent')}",
            f"  category:        {final_state.get('category')}",
            f"  temporal_scope:  {final_state.get('temporal_scope')}",
            f"  refined_query:   {final_state.get('refined_query')}",
            "\nRETRIEVAL:",
            f"  collection:      {settings.chroma_collection}",
            f"  top_k:           {settings.retrieval_top_k}",
            f"  retrieved_count: {len(retrieved_docs)}",
        ]
        for idx, doc in enumerate(retrieved_docs[:3], 1):
            meta = doc.metadata or {}
            preview = doc.page_content[:150].replace("\n", " ")
            debug_log.extend([
                f"\nRESULT {idx}:",
                f"  document:        {meta.get('document_name', 'Unknown')}",
                f"  page:            {meta.get('page', '?')}",
                f"  section:         {meta.get('section', 'N/A')}",
                f"  version:         {meta.get('version', '?')}",
                f"  status:          {meta.get('status', '?')}",
                f"  content_preview: {preview}...",
            ])
        debug_log.extend([
            "\nEVIDENCE VALIDATION:",
            f"  sufficient:      {final_state.get('evidence_sufficient')}",
            f"  confidence:      {final_state.get('evidence_confidence')}",
            f"  reason:          {final_state.get('evidence_reason')}",
            "\nCORRECTIVE RAG:",
            f"  triggered:       {final_state.get('retry_count', 0) > 0}",
            f"  refined_query:   {final_state.get('retrieval_query')}",
            f"  retry_count:     {final_state.get('retry_count', 0)}",
            "\nFINAL DECISION:",
            f"  {final_state.get('decision')}",
            "=" * 50 + "\n",
        ])
        print("\n".join(debug_log), flush=True)

        final_state["debug_info"] = {
            "retrieval_success": len(retrieved_docs) > 0,
            "chunks_retrieved": len(retrieved_docs),
            "evidence_status": "SUFFICIENT" if final_state.get("evidence_sufficient") else "INSUFFICIENT",
            "corrective_rag_used": final_state.get("retry_count", 0) > 0,
            "retry_count": final_state.get("retry_count", 0),
            "decision": final_state.get("decision", "REFUSE"),
        }

        return final_state

    except Exception as exc:
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        logger.error("agent_run_failed", query_id=query_id, error=str(exc))
        return {
            **initial_state,
            "answer": "I encountered an unexpected error. Please try again.",
            "decision": "REFUSE",
            "final_confidence": 0.0,
            "sources": [],
            "latency_ms": latency_ms,
            "error": str(exc),
        }
