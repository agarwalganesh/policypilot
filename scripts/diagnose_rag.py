#!/usr/bin/env python
"""
PolicyPilot — RAG Diagnostic Tool
Diagnoses the complete ingestion, embedding, vectorstore, retrieval, and validation pipeline.

Usage:
    python scripts/diagnose_rag.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings, configure_logging, get_logger
from backend.rag import vectorstore, retriever
from backend.rag.embeddings import get_embedding_model
from backend.rag.loaders import load_document
from backend.rag.metadata import extract_metadata, enrich_document_metadata
from backend.rag.chunking import get_chunker

settings = get_settings()
configure_logging("WARNING")  # keep stdout clean for diagnostic output


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def diagnose_chromadb():
    print_section("1. CHROMADB STATUS")
    try:
        client = vectorstore.get_chroma_client()
        collections = client.list_collections()
        col_names = [c.name for c in collections]
        print(f"Available Collections: {col_names}")

        store = vectorstore.get_vector_store()
        col = store._collection
        count = col.count()
        print(f"Target Collection:     {settings.chroma_collection}")
        print(f"Total Chunks:          {count}")

        if count == 0:
            print("⚠️  WARNING: ChromaDB collection is EMPTY! Document ingestion is required.")
            return False

        # Fetch sample chunk
        sample = col.get(limit=1, include=["documents", "metadatas"])
        if sample and sample["documents"]:
            doc_preview = sample["documents"][0][:180].replace("\n", " ")
            meta = sample["metadatas"][0] if sample["metadatas"] else {}
            print(f"\nSample Chunk:")
            print(f"  Document: {meta.get('document_name', 'Unknown')}")
            print(f"  Source:   {meta.get('source_file', 'Unknown')}")
            print(f"  Page:     {meta.get('page', '?')}")
            print(f"  Status:   {meta.get('status', 'Unknown')}")
            print(f"  Category: {meta.get('category', 'Unknown')}")
            print(f"  Preview:  {doc_preview}...")
        return True
    except Exception as exc:
        print(f"❌ ChromaDB Error: {exc}")
        return False


def diagnose_embeddings():
    print_section("2. EMBEDDINGS STATUS")
    print(f"Configured Model: {settings.gemini_embedding_model}")
    try:
        model = get_embedding_model()
        test_vec = model.embed_query("PolicyPilot test query")
        print(f"Embedding Generation:  ✅ SUCCESS")
        print(f"Vector Dimension:      {len(test_vec)}")
        return True
    except Exception as exc:
        print(f"Embedding Generation:  ❌ FAILED: {exc}")
        return False


def diagnose_pdf_extraction():
    print_section("3. PDF EXTRACTION & CHUNKING TEST")
    raw_dir = Path(settings.documents_raw_dir)
    leave_pdfs = list(raw_dir.glob("*Leave*.pdf"))
    if not leave_pdfs:
        print(f"⚠️  No Leave Policy PDF found in {raw_dir}")
        return

    sample_pdf = leave_pdfs[0]
    print(f"Testing file: {sample_pdf.name}")
    try:
        docs = load_document(str(sample_pdf))
        total_chars = sum(len(d.page_content) for d in docs)
        print(f"Pages loaded:           {len(docs)}")
        print(f"Total characters:       {total_chars}")

        meta = extract_metadata(str(sample_pdf))
        enriched = enrich_document_metadata(docs, meta)
        chunker = get_chunker("recursive")
        chunks = chunker.split(enriched)
        print(f"Chunks generated:       {len(chunks)}")

        if chunks:
            sample_chunk = chunks[0]
            print(f"Sample Chunk Metadata:  {sample_chunk.metadata}")
            preview = sample_chunk.page_content[:150].replace("\n", " ")
            print(f"Sample Chunk Preview:   {preview}...")
    except Exception as exc:
        print(f"❌ PDF Extraction failed: {exc}")


def diagnose_retrieval():
    print_section("4. DIRECT RETRIEVAL TESTS")
    test_queries = [
        "What is the leave policy at PW?",
        "What is casual leave?",
        "What is the probation period?",
        "What is the notice period?",
        "Can I claim internet reimbursement?",
        "What are the travel reimbursement rules?",
    ]

    for q in test_queries:
        print(f"\nQUERY: \"{q}\"")
        try:
            results = retriever.retrieve(query=q, user_role="employee", top_k=3)
            print(f"  Retrieved count: {len(results)}")
            if not results:
                print("  ⚠️  NO RESULTS RETURNED!")
            for idx, doc in enumerate(results, 1):
                d_name = doc.metadata.get("document_name", "Unknown")
                page = doc.metadata.get("page", "?")
                status = doc.metadata.get("status", "?")
                prev = doc.page_content[:120].replace("\n", " ")
                print(f"  [{idx}] {d_name} (Page {page}, Status: {status})")
                print(f"      Preview: {prev}...")
        except Exception as exc:
            print(f"  ❌ Retrieval failed: {exc}")


def main():
    print("=" * 60)
    print(" POLICYPILOT — RAG DIAGNOSTIC SUITE")
    print("=" * 60)
    chroma_ok = diagnose_chromadb()
    embed_ok = diagnose_embeddings()
    diagnose_pdf_extraction()
    diagnose_retrieval()
    print_section("DIAGNOSIS COMPLETE")


if __name__ == "__main__":
    main()
