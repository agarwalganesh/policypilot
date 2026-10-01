"""
PolicyPilot — Refusal Node
Generates a helpful refusal when evidence is insufficient.
Refusal is a FEATURE — it protects users from misinformation.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from backend.agents.state import AgentState
from backend.config import get_logger

logger = get_logger(__name__)

# Suggested policy categories for helpful refusal messages
POLICY_SUGGESTIONS = [
    "Leave Policy", "Attendance Policy", "Travel Reimbursement Policy",
    "Separation & Exit Policy", "IT Policy", "Code of Conduct",
    "Internet Reimbursement Policy", "PIP Policy", "Probation Policy",
]


def refusal_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Generate a helpful, professional refusal response.
    Called when evidence is insufficient after all retry attempts.
    """
    query = state["query"]
    reason = state.get("evidence_reason", "")
    retry_count = state.get("retry_count", 0)
    intent = state.get("intent", "policy_lookup")

    logger.info(
        "node_refusal",
        query_len=len(query),
        retry_count=retry_count,
        reason=reason,
    )

    # Choose refusal message based on context
    if state.get("access_denied"):
        refusal_msg = state.get("answer", "You don't have permission to access this information.")
    elif intent == "general" or not state.get("requires_policy_evidence"):
        refusal_msg = (
            "I'm PolicyPilot, an assistant specialized in Physics Wallah's internal company policies. "
            "I can only answer questions related to PW's official policy documents. "
            "Please try asking about a specific policy, such as leave, attendance, travel, or conduct."
        )
    else:
        refusal_msg = (
            "I couldn't find sufficient information in the available company policy documents "
            "to answer your question accurately.\n\n"
            "I don't want to guess or provide unsupported information about company policy.\n\n"
            "You may try asking about specific policies, such as:\n"
        )
        suggestions = POLICY_SUGGESTIONS[:5]
        for s in suggestions:
            refusal_msg += f"• {s}\n"
        refusal_msg += (
            "\nIf you believe this information should exist in our policy documents, "
            "please contact HR directly."
        )

    end_time = time.time()
    start_time = state.get("start_time", end_time)
    latency_ms = int((end_time - start_time) * 1000)

    return {
        "answer": refusal_msg,
        "decision": "REFUSE",
        "final_confidence": 0.0,
        "sources": [],
        "latency_ms": latency_ms,
    }
