#!/usr/bin/env python
"""
PolicyPilot — Google Gemini Connection Test
Verifies API key presence, client initialization, model accessibility,
and basic generation without leaking keys or credentials.

Usage:
    python scripts/test_gemini.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings, configure_logging

configure_logging("WARNING")
settings = get_settings()


def mask_key(key: str) -> str:
    """Mask key, showing only first 4 and last 4 characters."""
    if not key or len(key) < 10:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def test_gemini_connection() -> bool:
    print("=" * 60)
    print(" POLICYPILOT — GOOGLE GEMINI CONNECTION TEST")
    print("=" * 60)

    # 1. Verify GEMINI_API_KEY exists
    key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print("\n❌ 1. GEMINI_API_KEY Check: FAILED")
        print("   Reason: GEMINI_API_KEY (or GOOGLE_API_KEY) is not set in .env or environment.")
        print("   Please add to your .env file:")
        print("     GEMINI_API_KEY=your_actual_gemini_api_key_here")
        return False

    print(f"\n✅ 1. GEMINI_API_KEY Check: PASSED (Key: {mask_key(key)})")

    # 2. Test Client Initialization
    print(f"\nConfigured Model: {settings.gemini_model}")
    try:
        from backend.services.llm import get_llm
        llm = get_llm(temperature=0.0)
        print("✅ 2. Gemini Client Initialization: PASSED")
    except Exception as exc:
        print(f"❌ 2. Gemini Client Initialization: FAILED ({exc})")
        return False

    # 3. Test Generation
    print("\nTesting test generation...")
    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content="Respond with the single word: OK")])
        raw = response.content
        if isinstance(raw, list):
            content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
        else:
            content = str(raw)
        content = content.strip()
        print(f"✅ 3. Test Generation: PASSED")
        print(f"   Model Response: {content[:100]}")
    except Exception as exc:
        print(f"❌ 3. Test Generation: FAILED")
        print(f"   Error: {exc}")
        return False

    # 4. Test Embedding Model (if configured)
    print(f"\nConfigured Embedding Model: {settings.gemini_embedding_model}")
    try:
        from backend.services.llm import get_embedding_model
        embed_model = get_embedding_model()
        vec = embed_model.embed_query("PolicyPilot test query")
        print(f"✅ 4. Gemini Embeddings: PASSED (Dimension: {len(vec)})")
    except Exception as exc:
        print(f"⚠️  4. Gemini Embeddings Note: {exc}")

    print("\n" + "=" * 60)
    print(" ✅ GEMINI INTEGRATION VERIFICATION SUCCESSFUL")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_gemini_connection()
    sys.exit(0 if success else 1)
