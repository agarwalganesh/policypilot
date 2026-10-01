"""
PolicyPilot — Text Cleaning & Metadata Extraction
Normalizes extracted text and extracts structured policy metadata.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

from backend.config import get_logger

logger = get_logger(__name__)

# ── Document category mapping (based on PW policy inventory) ─
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "HR": [
        "leave", "attendance", "shift", "probation", "confirmation",
        "separation", "exit", "pip", "performance improvement",
        "comp off", "extra pay", "reassociation", "ijdp",
        "territorial army", "relatives", "wedding gift",
        "rewards", "recognition", "posh",
    ],
    "Finance": [
        "reimbursement", "travel", "meal", "hotel", "relocation",
        "internet", "variable pay", "retention pay", "vpf", "asset",
        "tds", "cheques", "gpa",
    ],
    "Compliance": [
        "aml", "anti money laundering", "anti-corruption", "corruption",
        "code of conduct", "code of business", "conflict of interest",
        "no gifts", "whistleblower", "equal opportunity",
        "social media", "escalate", "engage",
    ],
    "IT": [
        "it policy", "isms", "acceptable usage", "vibe coding",
        "deployment", "outbound email", "internet", "vulnerability",
        "ai sop", "tools vendor",
    ],
    "Benefits": [
        "group medical", "gtli", "pathshala", "vidyapeeth", "discounted",
        "insurance", "coverage",
    ],
    "Procurement": [
        "vendor", "onboarding", "sop", "tools",
    ],
    "Quality": [
        "test paper", "accuracy", "enhancement",
    ],
}

DEPARTMENT_MAPPING: Dict[str, str] = {
    "HR": "Human Resources",
    "Finance": "Finance & Accounts",
    "Compliance": "Legal & Compliance",
    "IT": "Information Technology",
    "Benefits": "Human Resources",
    "Procurement": "Procurement",
    "Quality": "Academic Quality",
}


def clean_text(text: str) -> str:
    """
    Normalize extracted text:
    - Remove excessive whitespace
    - Fix broken hyphenation
    - Remove null bytes
    - Normalize unicode
    """
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Normalize unicode
    text = text.encode("utf-8", errors="ignore").decode("utf-8")
    # Fix broken hyphenation (word-\nnext → wordnext)
    text = re.sub(r"-\n(\w)", r"\1", text)
    # Collapse multiple blank lines to two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove leading/trailing whitespace per line
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def infer_category(file_name: str, text_sample: str) -> str:
    """Infer policy category from filename and text content."""
    combined = (file_name + " " + text_sample[:500]).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return category
    return "General"


def infer_policy_name(file_name: str) -> str:
    """
    Convert raw filename to a clean policy name.
    Strips numeric prefixes, version suffixes, and copy indicators.
    """
    name = Path(file_name).stem
    # Remove numeric upload prefix (e.g. 1764592835_...)
    name = re.sub(r"^\d{8,}_", "", name)
    # Remove copy suffixes like (1), (2), (1)(1), etc.
    name = re.sub(r"(\s*\(\d+\))+\s*$", "", name)
    # Replace underscores and dashes with spaces
    name = name.replace("_", " ").replace("-", " ")
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    return name.strip().title()


def compute_file_hash(file_path: str) -> str:
    """Compute MD5 hash of file for duplicate detection."""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_metadata(
    file_path: str,
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build metadata dict for a document file.
    override: optional dict to merge (admin-supplied metadata takes priority).
    """
    path = Path(file_path)
    file_name = path.name
    policy_name = infer_policy_name(file_name)
    file_hash = compute_file_hash(file_path)
    file_size = path.stat().st_size

    # Try to detect version from filename (e.g. v1.0, v2, 2.0)
    version_match = re.search(r"v?(\d+\.\d+|\d+)", path.stem, re.IGNORECASE)
    version = version_match.group(0) if version_match else "1.0"

    # Try to detect draft status
    is_draft = "draft" in file_name.lower()
    status = "draft" if is_draft else "active"

    metadata: Dict[str, Any] = {
        "document_name": policy_name,
        "source_file": file_name,
        "file_hash": file_hash,
        "file_size_bytes": file_size,
        "file_type": path.suffix.lower().lstrip("."),
        "version": version,
        "status": status,
        "category": "General",  # will be refined after text load
        "department": "General",
        "effective_date": None,
        "last_updated": None,
        "access_roles": ["employee", "manager", "hr", "admin"],
    }

    if override:
        metadata.update({k: v for k, v in override.items() if v is not None})

    return metadata


def enrich_document_metadata(
    docs: List[Document],
    base_metadata: Dict[str, Any],
) -> List[Document]:
    """
    Merge base metadata into each page Document and infer category
    from the full text of the first page.
    """
    if docs:
        first_text = docs[0].page_content
        category = infer_category(base_metadata.get("source_file", ""), first_text)
        base_metadata["category"] = category
        base_metadata["department"] = DEPARTMENT_MAPPING.get(category, "General")

    enriched = []
    for doc in docs:
        merged = {**base_metadata, **doc.metadata}
        cleaned = clean_text(doc.page_content)
        if cleaned:
            enriched.append(Document(page_content=cleaned, metadata=merged))

    return enriched
