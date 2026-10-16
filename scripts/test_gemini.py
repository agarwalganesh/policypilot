#!/usr/bin/env python
"""
PolicyPilot — Migration forwarder: Gemini -> Groq
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_groq import test_groq_connection

if __name__ == "__main__":
    print("ℹ️ Note: PolicyPilot has been migrated to Groq API. Running test_groq.py...\n")
    success = test_groq_connection()
    sys.exit(0 if success else 1)
