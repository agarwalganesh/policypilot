#!/usr/bin/env python
"""
PolicyPilot — Document Ingestion Script
Ingests all PW policy documents from the raw directory into ChromaDB.

Usage:
    python scripts/ingest_documents.py
    python scripts/ingest_documents.py --dir /path/to/docs
    python scripts/ingest_documents.py --file /path/to/doc.pdf
    python scripts/ingest_documents.py --reindex
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import configure_logging, get_logger, get_settings
from backend.rag.ingestion import ingest_directory, ingest_document

settings = get_settings()
configure_logging()
logger = get_logger("ingest_script")

# Policy metadata overrides — use known metadata for PW documents
DOCUMENT_OVERRIDES = {
    "Anti Money Laundering (AML) Policy.pdf": {
        "document_name": "Anti Money Laundering (AML) Policy",
        "category": "Compliance",
        "department": "Legal & Compliance",
        "version": "1.0",
        "status": "active",
    },
    "Attendance and Shift Policy.pdf": {
        "document_name": "Attendance and Shift Policy",
        "category": "HR",
        "department": "Human Resources",
        "version": "1.0",
        "status": "active",
    },
    "1790256906_Leave_Policy_2026_-_Final_FTP_Updated593.pdf": {
        "document_name": "Leave Policy 2026",
        "category": "HR",
        "department": "Human Resources",
        "version": "2026",
        "status": "active",
    },
    "PROBATION-AND-CONFIRMATION-NEW-POLICY (1).pdf": {
        "document_name": "Probation and Confirmation Policy",
        "category": "HR",
        "department": "Human Resources",
        "version": "2.0",
        "status": "active",
    },
    "Separation & Exit Policy_Updated (1).pdf": {
        "document_name": "Separation and Exit Policy",
        "category": "HR",
        "department": "Human Resources",
        "version": "2.0",
        "status": "active",
    },
    "PW_ISMS - Acceptance Usage Policy v1.0.pdf": {
        "document_name": "Acceptable Usage Policy (ISMS)",
        "category": "IT",
        "department": "Information Technology",
        "version": "1.0",
        "status": "active",
    },
    "PW_ISMS - Vibe Coding and Deployment Policy v1.0.pdf": {
        "document_name": "Vibe Coding and Deployment Policy",
        "category": "IT",
        "department": "Information Technology",
        "version": "1.0",
        "status": "active",
    },
    "1773829923_Updated_document_-_AI_SOP_(1)671.docx": {
        "document_name": "AI Standard Operating Procedure",
        "category": "IT",
        "department": "Information Technology",
        "version": "1.0",
        "status": "active",
    },
    # DUPLICATES — mark as archived
    "GROUP MEDICAL COVERAGE POLICY.pdf": {
        "document_name": "Group Medical Coverage Policy",
        "category": "Benefits",
        "status": "archived",
    },
    "Updated document - AI SOP (1).docx": {
        "document_name": "AI Standard Operating Procedure",
        "category": "IT",
        "status": "archived",
    },
    "Test Paper Accuracy Enhancement Policy - Draft  (1) (1).pdf": {
        "document_name": "Test Paper Accuracy Enhancement Policy",
        "category": "Quality",
        "status": "draft",
    },
}


def main():
    parser = argparse.ArgumentParser(description="PolicyPilot Document Ingestion")
    parser.add_argument("--dir", default=None, help="Directory to ingest from")
    parser.add_argument("--file", default=None, help="Single file to ingest")
    parser.add_argument("--reindex", action="store_true", help="Re-index (delete existing chunks)")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        override = DOCUMENT_OVERRIDES.get(path.name, {})
        print(f"\n📄 Ingesting: {path.name}")
        result = ingest_document(str(path), override_metadata=override, reindex=args.reindex)
        if result.success:
            print(f"   ✅ Success — {result.chunk_count} chunks indexed")
        else:
            print(f"   ❌ Failed — {result.error}")
        return

    # Directory ingestion
    ingest_dir = args.dir or settings.documents_raw_dir
    print(f"\n🚀 PolicyPilot — Document Ingestion")
    print(f"   Directory: {ingest_dir}")
    print(f"   Reindex: {args.reindex}")
    print("=" * 60)

    dir_path = Path(ingest_dir)
    if not dir_path.exists():
        print(f"❌ Directory not found: {ingest_dir}")
        sys.exit(1)

    files = [
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower().lstrip(".") in settings.allowed_extensions_set
    ]
    print(f"   Found {len(files)} documents to process\n")

    success, failed = 0, 0
    for f in sorted(files):
        override = DOCUMENT_OVERRIDES.get(f.name, {})
        print(f"📄 {f.name[:60]:<60}", end=" ", flush=True)
        result = ingest_document(str(f), override_metadata=override, reindex=args.reindex)
        if result.success:
            print(f"✅ {result.chunk_count} chunks")
            success += 1
        else:
            print(f"❌ {result.error}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"✅ Success: {success}/{len(files)}")
    print(f"❌ Failed:  {failed}/{len(files)}")


if __name__ == "__main__":
    main()
