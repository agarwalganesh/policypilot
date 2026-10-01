"""
PolicyPilot — Access Checker Node
Validates that the user has permission to query this type of document.
Access is based on role + intent sensitivity.
"""
from __future__ import annotations

from typing import Any, Dict

from backend.agents.state import AgentState
from backend.auth.jwt_handler import ROLE_HIERARCHY
from backend.config import get_logger

logger = get_logger(__name__)

# Minimum role required to access each category
CATEGORY_MIN_ROLE: Dict[str, str] = {
    "HR": "employee",
    "Finance": "employee",
    "Compliance": "employee",
    "IT": "employee",
    "Benefits": "employee",
    "Procurement": "manager",
    "Quality": "employee",
    "General": "employee",
}

# Minimum role for high-sensitivity intents
SENSITIVITY_MIN_ROLE: Dict[str, str] = {
    "low": "employee",
    "medium": "employee",
    "high": "manager",
}


def access_checker_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Check whether the user has access to retrieve the requested policy category.
    Sets access_denied = True if unauthorized.
    """
    user_role = state.get("user_role", "employee")
    category = state.get("category") or "General"
    intent = state.get("intent", "policy_lookup")

    logger.info(
        "node_access_checker",
        user_role=user_role,
        category=category,
        intent=intent,
    )

    user_level = ROLE_HIERARCHY.get(user_role, 0)

    # Check category-level access
    min_role_for_category = CATEGORY_MIN_ROLE.get(category, "employee")
    required_level = ROLE_HIERARCHY.get(min_role_for_category, 1)

    if user_level < required_level:
        logger.warning(
            "access_denied",
            user_role=user_role,
            required_role=min_role_for_category,
            category=category,
        )
        return {
            "access_denied": True,
            "access_scope": [],
            "decision": "REFUSE",
            "answer": f"You don't have access to {category} policy documents. "
                      f"Minimum required role: {min_role_for_category}.",
        }

    logger.info("access_granted", user_role=user_role, category=category)
    return {
        "access_denied": False,
        "access_scope": [user_role],
    }
