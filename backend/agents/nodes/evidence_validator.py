"""
PolicyPilot — Evidence Validator Node
The most critical module: determines if retrieved evidence is
SUFFICIENT to answer the question.

Does NOT rely only on similarity scores.
Uses the LLM to evaluate semantic coverage and completeness.
"""
from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings
from backend.services.llm import get_llm

logger = get_logger(__name__)
settings = get_settings()

EVIDENCE_VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an evidence validation system for an enterprise policy assistant.

Your job is to determine whether the provided policy document excerpts contain
SUFFICIENT evidence to answer the user's question.

Rules:
1. Evidence is SUFFICIENT only if it DIRECTLY addresses the question
2. Related but non-specific content is NOT sufficient
3. Absence of evidence = insufficient (never hallucinate)
4. Partial evidence = insufficient if it doesn't cover the core question

Return JSON with these exact fields:
{{
  "sufficient": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation of your decision",
  "evidence_summary": "One sentence summary of what the evidence says (empty string if insufficient)",
  "supporting_chunks": ["chunk_id_1", "chunk_id_2"]
}}

Be strict. If you're unsure, return sufficient=false."""),
    ("human", """User Question: {query}

Retrieved Policy Evidence:
{evidence}

Does this evidence SUFFICIENTLY answer the question?"""),
])


def _format_evidence(docs: List[Document]) -> str:
    if not docs:
        return "No evidence retrieved."
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        name = meta.get("document_name", "Unknown Document")
        page = meta.get("page", "?")
        chunk_id = meta.get("chunk_id", f"chunk-{i}")
        parts.append(
            f"[{i}] Document: {name} | Page: {page} | Chunk ID: {chunk_id}\n"
            f"Content:\n{doc.page_content[:800]}\n"
        )
    return "\n---\n".join(parts)


def _get_llm():
    return get_llm(temperature=0.0, json_mode=True)


def evidence_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Evaluate whether retrieved documents sufficiently answer the query.
    Sets evidence_sufficient, evidence_confidence, evidence_reason.
    """
    docs = state.get("retrieved_documents", [])
    query = state["query"]

    logger.info("node_evidence_validator", chunks=len(docs))

    # Fast-path: no documents = insufficient
    if not docs:
        logger.info("evidence_insufficient_no_docs")
        return {
            "evidence_sufficient": False,
            "evidence_confidence": 0.0,
            "evidence_reason": "No relevant policy documents were found for this query.",
            "evidence_summary": "",
            "decision": "RETRIEVE_AGAIN",
        }

    evidence_text = _format_evidence(docs)

    try:
        chain = EVIDENCE_VALIDATION_PROMPT | _get_llm() | JsonOutputParser()
        result = chain.invoke({
            "query": query,
            "evidence": evidence_text,
        })

        sufficient = result.get("sufficient", False)
        confidence = float(result.get("confidence", 0.0))
        reason = result.get("reason", "")
        summary = result.get("evidence_summary", "")

        # Apply configurable threshold
        if confidence < settings.evidence_threshold:
            sufficient = False
            reason = f"Evidence confidence ({confidence:.2f}) below threshold ({settings.evidence_threshold})"

        logger.info(
            "evidence_validation_complete",
            sufficient=sufficient,
            confidence=confidence,
        )

        next_decision = "ANSWER" if sufficient else "RETRIEVE_AGAIN"

        return {
            "evidence_sufficient": sufficient,
            "evidence_confidence": confidence,
            "evidence_reason": reason,
            "evidence_summary": summary,
            "decision": next_decision,
        }

    except Exception as exc:
        logger.error("evidence_validator_failed", error=str(exc))
        # Conservative: treat as insufficient on error
        return {
            "evidence_sufficient": False,
            "evidence_confidence": 0.0,
            "evidence_reason": f"Evidence validation error: {str(exc)}",
            "evidence_summary": "",
            "decision": "RETRIEVE_AGAIN",
        }
