"""
PolicyPilot — LangGraph Agent State
TypedDict representing the full state of one agent invocation.
Every node reads from and writes to this state.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict

from langchain_core.documents import Document


class AgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────
    user_id: str
    user_role: str                     # employee | manager | hr | admin
    conversation_id: Optional[str]
    query_id: str

    # ── Query ─────────────────────────────────────────────────
    query: str
    conversation_history: List[Dict[str, str]]   # [{role, content}, ...]

    # ── Query Analysis ────────────────────────────────────────
    intent: Optional[str]
    category: Optional[str]
    temporal_scope: Literal["current", "historical", "unknown"]
    requires_policy_evidence: bool
    refined_query: Optional[str]

    # ── Access Control ────────────────────────────────────────
    access_scope: List[str]            # roles allowed for this query
    access_denied: bool

    # ── Retrieval ─────────────────────────────────────────────
    retrieved_documents: List[Document]
    retrieval_query: str               # actual query used for retrieval

    # ── Evidence Validation ───────────────────────────────────
    evidence_sufficient: bool
    evidence_confidence: float
    evidence_reason: str
    evidence_summary: str

    # ── Retry / Corrective RAG ────────────────────────────────
    retry_count: int
    max_retries: int

    # ── Answer ────────────────────────────────────────────────
    answer: Optional[str]
    raw_answer: Optional[str]          # before citation formatting
    answer_valid: bool
    answer_validation_reason: str

    # ── Citations ─────────────────────────────────────────────
    sources: List[Dict[str, Any]]

    # ── Final Decision ────────────────────────────────────────
    decision: Literal["ANSWER", "REFUSE", "RETRIEVE_AGAIN"]
    final_confidence: float

    # ── Observability ─────────────────────────────────────────
    agent_trace_id: Optional[str]
    start_time: float
    latency_ms: int
    error: Optional[str]
