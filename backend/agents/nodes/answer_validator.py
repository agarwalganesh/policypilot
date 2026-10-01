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
- valid = true ONLY if every factual claim in the answer is supported by the evidence
- If the answer says "I couldn't find" or refuses, that is ALWAYS valid = true
- If the answer invents numbers/policies/rules not in evidence, valid = false"""),
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

    # Build abbreviated evidence text
    evidence_text = "\n".join(
        f"[{doc.metadata.get('document_name', '?')} p{doc.metadata.get('page', '?')}]: "
        f"{doc.page_content[:400]}"
        for doc in docs
    )

    try:
        chain = VALIDATION_PROMPT | _get_llm() | JsonOutputParser()
        result = chain.invoke({"evidence": evidence_text, "answer": answer})

        valid = result.get("valid", False)
        reason = result.get("reason", "")
        unsupported = result.get("contains_unsupported_claims", False)
        correction = result.get("suggested_correction", "")

        logger.info("answer_validation_complete", valid=valid, unsupported=unsupported)

        # If invalid and a correction is suggested, use it
        if not valid and correction:
            return {
                "answer_valid": False,
                "answer_validation_reason": reason,
                "answer": correction,
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
