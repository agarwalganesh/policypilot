"""
PolicyPilot — Custom DeepEval Metrics

RefusalAccuracyMetric:
    Evaluates whether the system correctly refuses to answer
    questions that lack policy evidence support.
"""
from __future__ import annotations

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

REFUSAL_INDICATORS = [
    "i couldn't find",
    "i don't want to guess",
    "insufficient information",
    "not found in",
    "available company policy documents",
    "please contact hr",
    "no information",
    "cannot find",
    "not available",
    "i'm unable to find",
]

HALLUCINATION_INDICATORS = [
    "according to pw policy",
    "pw provides",
    "employees are entitled to",
    "the policy states",
    "you can claim",
    "pw offers",
    "employees receive",
]


class RefusalAccuracyMetric(BaseMetric):
    """
    Custom metric: Measures whether the system correctly refuses
    to answer unanswerable questions.

    Score = 1.0 if the answer contains refusal indicators
    Score = 0.0 if the answer appears to provide fabricated policy information
    """

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.name = "Refusal Accuracy"
        self.score = 0.0
        self.reason = ""
        self.success = False

    def measure(self, test_case: LLMTestCase) -> float:
        answer = test_case.actual_output.lower()

        # Check for refusal indicators
        has_refusal = any(ind in answer for ind in REFUSAL_INDICATORS)

        # Check for hallucination indicators (bad — answer should not be authoritative)
        has_hallucination = any(ind in answer for ind in HALLUCINATION_INDICATORS)

        if has_refusal and not has_hallucination:
            self.score = 1.0
            self.reason = "Correctly refused with appropriate refusal language"
        elif has_hallucination:
            self.score = 0.0
            self.reason = f"FAIL: Answer appears to fabricate policy information"
        elif not has_refusal:
            self.score = 0.2
            self.reason = "Answer does not clearly refuse — borderline case"
        else:
            self.score = 0.5
            self.reason = "Partial refusal detected"

        self.success = self.score >= self.threshold
        return self.score

    def is_successful(self) -> bool:
        return self.success

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)
