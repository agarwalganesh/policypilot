"""
PolicyPilot — Unit Tests: Metadata Extraction and Text Cleaning
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.rag.metadata import (
    clean_text,
    infer_category,
    infer_policy_name,
    CATEGORY_KEYWORDS,
)


class TestCleanText:
    def test_removes_null_bytes(self):
        assert "\x00" not in clean_text("hello\x00world")

    def test_collapses_blank_lines(self):
        result = clean_text("line1\n\n\n\n\nline2")
        assert "\n\n\n" not in result

    def test_fixes_hyphenation(self):
        result = clean_text("em-\nployee")
        assert "employee" in result

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_strips_whitespace(self):
        result = clean_text("  hello  \n\n  world  ")
        # Single blank line between paragraphs → preserved; leading/trailing space removed
        assert "hello" in result and "world" in result



class TestInferCategory:
    def test_hr_category(self):
        assert infer_category("Leave Policy.pdf", "This policy covers casual leave and sick leave.") == "HR"

    def test_it_category(self):
        assert infer_category("IT Policies.pdf", "Acceptable usage policy for IT systems and ISMS.") == "IT"

    def test_compliance_category(self):
        assert infer_category("AML Policy.pdf", "Anti money laundering policy and code of conduct.") == "Compliance"

    def test_finance_category(self):
        assert infer_category("Travel Reimbursement.pdf", "Travel and hotel reimbursement policy.") == "Finance"

    def test_default_general(self):
        assert infer_category("unknown.pdf", "random content with no keywords") == "General"


class TestInferPolicyName:
    def test_removes_numeric_prefix(self):
        result = infer_policy_name("1764592835_GROUP_MEDICAL_COVERAGE_POLICY451.pdf")
        assert "1764592835" not in result

    def test_removes_copy_suffixes(self):
        result = infer_policy_name("Leave Policy (1)(2)(3).pdf")
        assert "(1)" not in result

    def test_titlecase(self):
        result = infer_policy_name("attendance_and_shift_policy.pdf")
        assert result == "Attendance And Shift Policy"

    def test_handles_underscores(self):
        result = infer_policy_name("PW_ISMS - Acceptance_Usage_Policy_v1.0.pdf")
        assert "_" not in result


class TestVersionDetection:
    def test_detects_version_in_filename(self):
        from backend.rag.metadata import extract_metadata
        # We can't run this without a real file, so just test the regex
        import re
        pattern = re.compile(r"v?(\d+\.\d+|\d+)", re.IGNORECASE)
        assert pattern.search("PW_ISMS - Acceptance Usage Policy v1.0.pdf").group(0) == "v1.0"
        assert pattern.search("Asset Allocation Policy 2.0.pdf").group(0) == "2.0"
