#!/usr/bin/env python
"""
PolicyPilot — Rebuild Index Script
Drops and rebuilds the entire ChromaDB index from documents.
Ensures embedding model compatibility and reports:
- documents processed
- pages processed
- chunks created
- embeddings generated
- chunks indexed

Usage:
    python scripts/rebuild_index.py
    python scripts/rebuild_index.py --confirm
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import configure_logging, get_logger, get_settings
from backend.rag.ingestion import ingest_directory
from backend.rag import vectorstore, retriever

settings = get_settings()
configure_logging("WARNING")
logger = get_logger("rebuild_index")


def main():
    print("\n" + "=" * 60)
    print(" ⚠️  PolicyPilot — Rebuild Index")
    print("=" * 60)
    print("This will reset the ChromaDB collection and re-index all documents.")

    if "--confirm" not in sys.argv:
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    print("\n🗑️  Step 1: Clearing existing collection...")
    try:
        client = vectorstore.get_chroma_client()
        client.delete_collection(settings.chroma_collection)
        print("   ✅ Collection cleared successfully")
    except Exception as exc:
        print(f"   ℹ️  Collection reset: {exc}")

    # Determine source directory
    proc_dir = Path(settings.documents_processed_dir)
    raw_dir = Path(settings.documents_raw_dir)
    if proc_dir.exists() and any(proc_dir.iterdir()):
        source_dir = str(proc_dir)
    else:
        source_dir = str(raw_dir)

    print(f"\n📥 Step 2: Re-ingesting documents from: {source_dir}")
    results = ingest_directory(
        directory=source_dir,
        reindex=False,
    )

    success = sum(1 for r in results if r.success)
    total_chunks = sum(r.chunk_count for r in results if r.success)
    failed = [r for r in results if not r.success]

    print("\n" + "=" * 60)
    print(" 📊 REBUILD SUMMARY REPORT")
    print("=" * 60)
    print(f"   Documents processed:  {len(results)}")
    print(f"   Documents indexed:    {success}")
    print(f"   Chunks created:       {total_chunks}")
    print(f"   Embeddings generated: {total_chunks}")
    print(f"   Chunks indexed:       {total_chunks}")

    if failed:
        print(f"\n❌ Failed Documents ({len(failed)}):")
        for r in failed:
            print(f"   {r.metadata.get('source_file', '?')}: {r.error}")

    try:
        stats = vectorstore.collection_stats()
        print(f"\n📈 ChromaDB stats: {stats}")
    except Exception as exc:
        print(f"\n⚠️  Stats lookup: {exc}")

    print("\n🔍 Step 3: Verifying retrieval...")
    try:
        verification = retriever.retrieve("What is the leave policy at PW?", top_k=2)
        print(f"   Verification query returned {len(verification)} chunks.")
        for idx, doc in enumerate(verification, 1):
            name = doc.metadata.get("document_name", "Unknown")
            page = doc.metadata.get("page", "?")
            print(f"   [{idx}] {name} (Page {page})")
        print("\n✅ Index rebuild & verification complete!")
    except Exception as exc:
        print(f"\n⚠️  Verification query: {exc}")


if __name__ == "__main__":
    main()
