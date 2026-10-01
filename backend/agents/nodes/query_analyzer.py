"""
PolicyPilot — Query Analyzer Node
Analyzes the user's query to extract intent, category, and temporal scope.
Uses structured output to enforce consistent decision format.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.state import AgentState
from backend.config import get_logger, get_settings
from backend.services.llm import get_llm

logger = get_logger(__name__)
settings = get_settings()

QUERY_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a query analyzer for an enterprise policy assistant.
Analyze the user's query and return a JSON object with these exact fields:
{{
  "intent": "policy_lookup | clarification | historical | general",
  "category": "HR | Finance | Compliance | IT | Benefits | Procurement | Quality | General",
  "entities": ["list", "of", "key", "entities"],
  "temporal_scope": "current | historical | unknown",
  "requires_policy_evidence": true or false,
  "refined_query": "cleaned, keyword-focused version of the query for retrieval",
  "access_sensitivity": "low | medium | high"
}}

Rules:
- If the query is about current policy, temporal_scope = "current"
- If it asks "what WAS the policy in 2024", temporal_scope = "historical"
- If the query is clearly out of scope (weather, sports), requires_policy_evidence = false
- refined_query should remove conversational filler and focus on policy keywords

Return ONLY valid JSON. No explanation."""),
    ("human", "Query: {query}\n\nConversation context: {context}"),
])


def _get_llm():
    return get_llm(temperature=0.0, json_mode=True)


def query_analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Analyze the query and extract structured intent.
    """
    logger.info("node_query_analyzer", query_len=len(state["query"]))

    # Build conversation context summary
    history = state.get("conversation_history", [])
    context_str = ""
    if history:
        last_turns = history[-4:]  # Last 2 exchanges
        context_str = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in last_turns)

    try:
        chain = QUERY_ANALYSIS_PROMPT | _get_llm() | JsonOutputParser()
        analysis = chain.invoke({
            "query": state["query"],
            "context": context_str or "No previous context.",
        })

        # Validate and apply defaults
        intent = analysis.get("intent", "policy_lookup")
        category = analysis.get("category", "General")
        temporal_scope = analysis.get("temporal_scope", "current")
        requires_evidence = analysis.get("requires_policy_evidence", True)
        refined_query = analysis.get("refined_query", state["query"])
        entities = analysis.get("entities", [])

        logger.info(
            "query_analysis_complete",
            intent=intent,
            category=category,
            temporal_scope=temporal_scope,
            requires_evidence=requires_evidence,
        )

        return {
            "intent": intent,
            "category": category if category in ["HR", "Finance", "Compliance", "IT", "Benefits", "Procurement", "Quality"] else None,
            "temporal_scope": temporal_scope if temporal_scope in ["current", "historical", "unknown"] else "current",
            "requires_policy_evidence": requires_evidence,
            "refined_query": refined_query,
            "retrieval_query": refined_query,
        }

    except Exception as exc:
        logger.error("query_analyzer_failed", error=str(exc))
        # Fallback: use original query
        return {
            "intent": "policy_lookup",
            "category": None,
            "temporal_scope": "current",
            "requires_policy_evidence": True,
            "refined_query": state["query"],
            "retrieval_query": state["query"],
        }
