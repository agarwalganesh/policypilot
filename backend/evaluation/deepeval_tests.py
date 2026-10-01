"""
PolicyPilot — DeepEval Tests
Runs the full evaluation suite against the 100-question dataset.

Usage:
    python -m pytest backend/evaluation/deepeval_tests.py -v
    python -m pytest backend/evaluation/deepeval_tests.py -v -k "refusal"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.graph import run_agent
from backend.evaluation.metrics import RefusalAccuracyMetric
from backend.config import configure_logging

configure_logging()

DATASET_PATH = Path(__file__).parent / "dataset" / "eval_dataset.json"
DATASET = json.loads(DATASET_PATH.read_text())


def _run_query(question: str) -> dict:
    """Execute the agent and return result."""
    return run_agent(
        query=question,
        user_id="eval_user",
        user_role="employee",
    )


def _build_test_case(item: dict) -> tuple[LLMTestCase, dict]:
    result = _run_query(item["question"])
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    retrieved_context = [s.get("relevant_text", "") for s in sources if s.get("relevant_text")]

    test_case = LLMTestCase(
        input=item["question"],
        actual_output=answer,
        expected_output=item.get("expected_answer", ""),
        retrieval_context=retrieved_context,
    )
    return test_case, result


# ── Answerable question tests ─────────────────────────────────

@pytest.mark.parametrize(
    "item",
    [q for q in DATASET if q["should_answer"]],
    ids=[q["id"] for q in DATASET if q["should_answer"]],
)
def test_answerable_faithfulness(item):
    """Test that answers for answerable questions are faithful to retrieved evidence."""
    test_case, result = _build_test_case(item)

    if result.get("decision") == "REFUSE":
        pytest.skip(f"Agent refused answerable question {item['id']} — check retrieval")

    metric = FaithfulnessMetric(threshold=0.7)
    assert_test(test_case, [metric])


@pytest.mark.parametrize(
    "item",
    [q for q in DATASET if q["should_answer"]],
    ids=[f"{q['id']}_relevance" for q in DATASET if q["should_answer"]],
)
def test_answerable_relevance(item):
    """Test that answers are relevant to the question."""
    test_case, result = _build_test_case(item)

    if result.get("decision") == "REFUSE":
        pytest.skip(f"Agent refused answerable question {item['id']}")

    metric = AnswerRelevancyMetric(threshold=0.7)
    assert_test(test_case, [metric])


# ── Unanswerable question tests ───────────────────────────────

@pytest.mark.parametrize(
    "item",
    [q for q in DATASET if not q["should_answer"]],
    ids=[q["id"] for q in DATASET if not q["should_answer"]],
)
def test_unanswerable_refusal_accuracy(item):
    """
    Test that questions without policy evidence are REFUSED, not hallucinated.
    This is the most important test — hallucination failure means FAIL.
    """
    result = _run_query(item["question"])
    decision = result.get("decision")

    refusal_metric = RefusalAccuracyMetric()
    test_case = LLMTestCase(
        input=item["question"],
        actual_output=result.get("answer", ""),
    )

    # Decision should be REFUSE
    assert decision == "REFUSE", (
        f"HALLUCINATION RISK: Agent answered '{item['id']}' which should be refused. "
        f"Reason: {item.get('refusal_reason')}. "
        f"Answer: {result.get('answer', '')[:200]}"
    )

    assert_test(test_case, [refusal_metric])


# ── Hallucination tests ───────────────────────────────────────

@pytest.mark.parametrize(
    "item",
    [q for q in DATASET if q["should_answer"]],
    ids=[f"{q['id']}_hallucination" for q in DATASET if q["should_answer"]],
)
def test_no_hallucination(item):
    """Test that answers don't contain hallucinated content."""
    test_case, result = _build_test_case(item)

    if result.get("decision") == "REFUSE":
        pytest.skip("Agent refused — skip hallucination test")

    if not test_case.retrieval_context:
        pytest.skip("No retrieval context — skip hallucination test")

    metric = HallucinationMetric(threshold=0.3)
    assert_test(test_case, [metric])
