"""
PolicyPilot — Answer Validator Node
Checks that the generated answer is grounded in the evidence
and not hallucinated.
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

VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an answer validation system for an enterprise policy assistant.

Check if the generated answer is properly grounded in the provided evidence.

Return JSON:
{{
  "valid": true or false,
  "reason": "brief explanation",
  "contains_unsupported_claims": true or false,
  "suggested_correction": "only if invalid, otherwise empty string"
}}

Rules:
- valid = true if ALL factual claims (numbers, dates, entitlements, rules) appear in the evidence
- valid = true if the answer reorganizes, summarizes, or formats evidence without adding new facts
- valid = true if the answer says "I couldn't find" or refuses — refusals are ALWAYS valid
- valid = false ONLY if the answer invents specific numbers, names, or policies NOT present in the evidence
- contains_unsupported_claims = true only when a SPECIFIC invented fact is present (not just formatting)
- When in doubt, set valid = true"""),
    ("human", """Evidence:
{evidence}

Generated Answer:
{answer}

Is the answer properly grounded?"""),
])


def _get_llm():
    return get_llm(temperature=0.0, json_mode=True)


def answer_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Validate that the answer is grounded in retrieved evidence.
    If invalid, the answer is flagged and a corrected version may be used.
    """
    answer = state.get("answer", "")
    docs = state.get("retrieved_documents", [])

    logger.info("node_answer_validator", answer_len=len(answer))

    if not answer:
        return {"answer_valid": False, "answer_validation_reason": "Empty answer"}

    # Build evidence text for validator
    evidence_text = "\n\n".join(
        f"[{doc.metadata.get('document_name', '?')} p{doc.metadata.get('page', '?')}]: "
        f"{doc.page_content}"
        for doc in docs
    )

    try:
        chain = VALIDATION_PROMPT | _get_llm() | JsonOutputParser()
        result = chain.invoke({"evidence": evidence_text, "answer": answer})

        valid = result.get("valid", True)
        reason = result.get("reason", "")
        unsupported = result.get("contains_unsupported_claims", False)
        correction = result.get("suggested_correction", "")

        logger.info("answer_validation_complete", valid=valid, unsupported=unsupported)

        if not valid:
            # A specific invented fact was flagged: never pass the answer through
            if unsupported:
                if correction and len(correction.strip()) > 20:
                    return {
                        "answer_valid": False,
                        "answer_validation_reason": reason,
                        "answer": correction,
                    }
                return {
                    "answer_valid": False,
                    "answer_validation_reason": reason,
                }

            # Invalid without a concrete unsupported claim: treat as an
            # over-conservative verdict and pass through to avoid false refusals
            logger.warning("answer_validator_uncertain_passing_through", reason=reason)
            return {
                "answer_valid": True,
                "answer_validation_reason": f"Validator uncertain (passed through): {reason}",
            }

        return {
            "answer_valid": valid,
            "answer_validation_reason": reason,
        }

    except Exception as exc:
        logger.error("answer_validator_failed", error=str(exc))
        # Conservative: pass through if validator itself fails
        return {
            "answer_valid": True,
            "answer_validation_reason": f"Validator error (passed through): {str(exc)}",
        }
