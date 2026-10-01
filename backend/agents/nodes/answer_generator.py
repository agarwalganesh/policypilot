"""
PolicyPilot — Answer Generator Node
Generates answers ONLY from validated evidence.
System prompt enforces strict evidence-grounding.
"""
from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings
from backend.services.llm import get_llm

logger = get_logger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are PolicyPilot, an enterprise policy assistant for Physics Wallah (PW).

CRITICAL RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. Answer ONLY from the policy evidence provided below. Never use your general knowledge.
2. If the evidence doesn't support the answer, say "I couldn't find this information in the available policy documents."
3. Never invent numbers, dates, durations, or policy details.
4. Be concise and precise. Employees rely on this for compliance.
5. When the policy is clear, state it directly. Don't hedge unnecessarily.
6. If multiple policies are relevant, synthesize them clearly.
7. Use the employee's conversational context but NEVER treat past conversation as policy truth.

FORMAT RULES:
- Start directly with the answer. No preamble.
- Use bullet points for lists of entitlements or steps.
- Keep answers under 300 words unless the policy is genuinely complex.
- Do NOT include citation markers in the answer text (citations are added separately).

EVIDENCE PROVIDED:
{evidence}
"""

HUMAN_PROMPT = """Question: {query}

Previous conversation context:
{context}

Answer based only on the evidence above:"""


def _build_evidence_context(docs: List[Document]) -> str:
    if not docs:
        return "No evidence available."
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        name = meta.get("document_name", "Unknown")
        page = meta.get("page", "?")
        parts.append(f"[Source {i}: {name}, Page {page}]\n{doc.page_content[:600]}")
    return "\n\n".join(parts)


def _build_conversation_context(history: List[Dict]) -> str:
    if not history:
        return "No previous conversation."
    return "\n".join(f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-4:])


def _get_llm():
    return get_llm(temperature=0.1)


def answer_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Generate an answer from validated evidence only.
    """
    docs = state.get("retrieved_documents", [])
    query = state["query"]
    history = state.get("conversation_history", [])

    logger.info("node_answer_generator", chunks=len(docs))

    evidence = _build_evidence_context(docs)
    context = _build_conversation_context(history)

    system_msg = SystemMessage(content=SYSTEM_PROMPT.format(evidence=evidence))
    human_msg = HumanMessage(content=HUMAN_PROMPT.format(query=query, context=context))

    try:
        llm = _get_llm()
        response = llm.invoke([system_msg, human_msg])
        raw = response.content
        if isinstance(raw, list):
            raw_answer = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
        else:
            raw_answer = str(raw)
        raw_answer = raw_answer.strip()

        logger.info("answer_generated", answer_len=len(raw_answer))
        return {
            "raw_answer": raw_answer,
            "answer": raw_answer,  # citation_generator will augment this
        }

    except Exception as exc:
        logger.error("answer_generator_failed", error=str(exc))
        return {
            "raw_answer": "",
            "answer": "I encountered an error generating the response. Please try again.",
            "answer_valid": False,
        }
