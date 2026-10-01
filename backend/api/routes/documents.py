"""
PolicyPilot — Document Management Routes
POST /documents/upload
GET  /documents
GET  /documents/<id>
POST /documents/<id>/archive
POST /documents/<id>/reindex
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Blueprint, g, jsonify, request

from backend.auth.decorators import login_required, role_required
from backend.config import get_logger, get_settings
from backend.database import get_db, Document, DocumentVersion
from backend.rag.ingestion import ingest_document
from backend.rag.metadata import compute_file_hash, infer_policy_name
from backend.rag import vectorstore

logger = get_logger(__name__)
settings = get_settings()
documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


def _safe_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:80]


@documents_bp.post("/upload")
@role_required("hr")
def upload_document():
    """
    Upload a new policy document.
    Requires HR role or above.
    Triggers ingestion pipeline.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions_set:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 422

    # Secure the filename
    safe_name = secure_filename(file.filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 422

    # Read override metadata from form
    form = request.form
    policy_name = form.get("name") or infer_policy_name(file.filename)
    category = form.get("category")
    department = form.get("department")
    version = form.get("version", "1.0")
    status = form.get("status", "active")
    notes = form.get("notes")

    # Save to raw directory
    raw_dir = Path(settings.documents_raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    save_path = raw_dir / safe_name

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > settings.max_upload_size_bytes:
        return jsonify({"error": f"File too large. Max {settings.max_upload_size_mb}MB"}), 413

    file.save(str(save_path))

    # Compute hash for duplicate detection
    file_hash = compute_file_hash(str(save_path))

    with get_db() as db:
        # Check for duplicate hash
        existing_version = db.query(DocumentVersion).filter_by(file_hash=file_hash).first()
        if existing_version:
            return jsonify({
                "warning": "Duplicate file detected (identical content already indexed)",
                "existing_version_id": str(existing_version.id),
                "existing_document_id": str(existing_version.document_id),
            }), 409

        # Find or create Document record
        slug = _safe_slug(policy_name)
        doc = db.query(Document).filter_by(slug=slug).first()
        if not doc:
            doc = Document(
                name=policy_name,
                slug=slug,
                category=category,
                department=department,
            )
            db.add(doc)
            db.flush()

        # Archive existing active version if new upload
        if status == "active":
            db.query(DocumentVersion).filter_by(
                document_id=str(doc.id), status="active"
            ).update({"status": "archived"})

        # Create version record (pre-ingestion)
        doc_version = DocumentVersion(
            document_id=str(doc.id),
            version=version,
            status=status,
            source_file=safe_name,
            file_hash=file_hash,
            access_roles=["employee", "manager", "hr", "admin"],
            uploaded_by=g.user_id,
            notes=notes,
        )
        db.add(doc_version)
        db.flush()
        version_id = str(doc_version.id)

    # Run ingestion pipeline
    override_metadata = {
        "document_name": policy_name,
        "category": category,
        "department": department,
        "version": version,
        "status": status,
    }
    result = ingest_document(str(save_path), override_metadata=override_metadata)

    # Update version record with ingestion result
    with get_db() as db:
        dv = db.query(DocumentVersion).filter_by(id=version_id).first()
        if dv:
            dv.chunk_count = result.chunk_count
            dv.indexed = result.success

    if result.success:
        logger.info("document_upload_complete", policy=policy_name, chunks=result.chunk_count)
        return jsonify({
            "success": True,
            "document_id": str(doc.id),
            "version_id": version_id,
            "policy_name": policy_name,
            "chunk_count": result.chunk_count,
        }), 201
    else:
        return jsonify({"error": result.error or "Ingestion failed"}), 500


@documents_bp.get("")
@login_required
def list_documents():
    """List all documents with their active version info."""
    with get_db() as db:
        docs = db.query(Document).order_by(Document.name).all()
        result = []
        for doc in docs:
            active_v = next((v for v in doc.versions if v.status == "active"), None)
            result.append({
                "id": str(doc.id),
                "name": doc.name,
                "slug": doc.slug,
                "category": doc.category,
                "department": doc.department,
                "active_version": active_v.version if active_v else None,
                "status": active_v.status if active_v else "no_version",
                "chunk_count": active_v.chunk_count if active_v else 0,
                "indexed": active_v.indexed if active_v else False,
                "effective_date": str(active_v.effective_date) if active_v and active_v.effective_date else None,
                "updated_at": doc.updated_at.isoformat(),
            })
        return jsonify(result)


@documents_bp.get("/<document_id>")
@login_required
def get_document(document_id: str):
    """Get document with all versions."""
    with get_db() as db:
        doc = db.query(Document).filter_by(id=document_id).first()
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        return jsonify({
            "id": str(doc.id),
            "name": doc.name,
            "category": doc.category,
            "department": doc.department,
            "created_at": doc.created_at.isoformat(),
            "versions": [{
                "id": str(v.id),
                "version": v.version,
                "status": v.status,
                "effective_date": str(v.effective_date) if v.effective_date else None,
                "source_file": v.source_file,
                "chunk_count": v.chunk_count,
                "indexed": v.indexed,
                "uploaded_at": v.uploaded_at.isoformat(),
                "notes": v.notes,
            } for v in doc.versions],
        })


@documents_bp.post("/<document_id>/archive")
@role_required("hr")
def archive_document(document_id: str):
    """Archive a document's active version."""
    with get_db() as db:
        doc = db.query(Document).filter_by(id=document_id).first()
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        updated = db.query(DocumentVersion).filter_by(
            document_id=document_id, status="active"
        ).update({"status": "archived"})

        return jsonify({"success": True, "archived_versions": updated})


@documents_bp.post("/<document_id>/reindex")
@role_required("admin")
def reindex_document(document_id: str):
    """Re-index all chunks for a document's active version."""
    with get_db() as db:
        doc = db.query(Document).filter_by(id=document_id).first()
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        active_v = db.query(DocumentVersion).filter_by(
            document_id=document_id, status="active"
        ).first()
        if not active_v:
            return jsonify({"error": "No active version found"}), 404

        source_file = active_v.source_file

    # Delete old chunks
    vectorstore.delete_by_source_file(source_file)

    # Re-ingest from processed directory
    processed_path = Path(settings.documents_processed_dir) / source_file
    if not processed_path.exists():
        return jsonify({"error": f"Source file not found: {source_file}"}), 404

    result = ingest_document(str(processed_path), reindex=True)

    with get_db() as db:
        dv = db.query(DocumentVersion).filter_by(id=str(active_v.id)).first()
        if dv:
            dv.chunk_count = result.chunk_count
            dv.indexed = result.success

    return jsonify({
        "success": result.success,
        "chunk_count": result.chunk_count,
        "error": result.error,
    })


@documents_bp.get("/stats")
@login_required
def document_stats():
    """Return vector store and document statistics."""
    stats = vectorstore.collection_stats()
    with get_db() as db:
        total = db.query(Document).count()
        active = db.query(DocumentVersion).filter_by(status="active").count()
        archived = db.query(DocumentVersion).filter_by(status="archived").count()
        draft = db.query(DocumentVersion).filter_by(status="draft").count()

    return jsonify({
        "total_documents": total,
        "active_versions": active,
        "archived_versions": archived,
        "draft_versions": draft,
        "vectorstore": stats,
    })
