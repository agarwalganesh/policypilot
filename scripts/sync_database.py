#!/usr/bin/env python
"""
PolicyPilot — Sync Database with ChromaDB and Raw Documents
Populates Document and DocumentVersion in SQLite for all indexed policies.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.database import get_db, Document, DocumentVersion
from backend.rag import vectorstore
from backend.rag.metadata import infer_policy_name, infer_category, compute_file_hash
from scripts.ingest_documents import DOCUMENT_OVERRIDES

settings = get_settings()


def sync_db():
    print("=" * 60)
    print(" POLICYPILOT — SYNC DATABASE WITH CHROMADB")
    print("=" * 60)

    client = vectorstore.get_chroma_client()
    collection = client.get_collection(settings.chroma_collection)
    data = collection.get()

    metadatas = data.get("metadatas") or []
    print(f"Total chunks in ChromaDB: {len(metadatas)}")

    # Aggregate by source_file
    files_meta = defaultdict(dict)
    file_chunk_counts = Counter()

    for m in metadatas:
        if not m:
            continue
        sf = m.get("source_file")
        if not sf:
            continue
        file_chunk_counts[sf] += 1
        # store latest/first metadata seen
        if sf not in files_meta:
            files_meta[sf] = m

    print(f"Unique indexed files: {len(files_meta)}")

    raw_dir = Path(settings.documents_raw_dir)

    with get_db() as db:
        synced_count = 0
        for source_file, meta in files_meta.items():
            doc_name = meta.get("document_name") or infer_policy_name(source_file)
            category = meta.get("category") or "General"
            department = meta.get("department") or "General"
            version_str = str(meta.get("version") or "1.0")
            status = meta.get("status") or "active"

            file_path = raw_dir / source_file
            file_hash = meta.get("file_hash")
            if not file_hash and file_path.exists():
                file_hash = compute_file_hash(str(file_path))

            chunk_count = file_chunk_counts[source_file]

            # Find matching Document by slug or name
            from backend.api.routes.documents import _safe_slug
            slug = _safe_slug(doc_name)

            doc = db.query(Document).filter((Document.slug == slug) | (Document.name == doc_name)).first()
            if not doc:
                # Also try matching by stripped name
                doc = Document(
                    name=doc_name,
                    slug=slug,
                    category=category,
                    department=department,
                )
                db.add(doc)
                db.flush()

            # Check if DocumentVersion exists
            doc_version = db.query(DocumentVersion).filter_by(
                document_id=str(doc.id),
                source_file=source_file,
            ).first()

            if not doc_version:
                doc_version = DocumentVersion(
                    document_id=str(doc.id),
                    version=version_str,
                    status=status,
                    source_file=source_file,
                    file_hash=file_hash,
                    chunk_count=chunk_count,
                    indexed=True,
                    access_roles=meta.get("access_roles") if isinstance(meta.get("access_roles"), list) else ["employee", "manager", "hr", "admin"],
                )
                db.add(doc_version)
            else:
                doc_version.version = version_str
                doc_version.status = status
                doc_version.chunk_count = chunk_count
                doc_version.indexed = True
                if file_hash:
                    doc_version.file_hash = file_hash

            synced_count += 1

        db.commit()

        total_docs = db.query(Document).count()
        total_active_versions = db.query(DocumentVersion).filter_by(status="active").count()
        total_versions = db.query(DocumentVersion).count()

        print(f"\n✅ Synced {synced_count} files into SQLite!")
        print(f"   Total Documents in DB: {total_docs}")
        print(f"   Active Document Versions: {total_active_versions}")
        print(f"   Total Document Versions: {total_versions}")


if __name__ == "__main__":
    sync_db()
