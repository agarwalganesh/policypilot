"""
PolicyPilot — Full Document Ingestion Pipeline
PDF/DOCX → Load → Clean → Chunk → Embed → ChromaDB
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

from backend.config import get_logger, get_settings
from backend.rag.chunking import get_chunker
from backend.rag.loaders import load_document
from backend.rag.metadata import compute_file_hash, enrich_document_metadata, extract_metadata
from backend.rag import vectorstore

logger = get_logger(__name__)
settings = get_settings()


class IngestionResult:
    def __init__(self):
        self.success: bool = False
        self.chunk_count: int = 0
        self.chunk_ids: List[str] = []
        self.file_hash: str = ""
        self.metadata: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "chunk_count": self.chunk_count,
            "chunk_ids": self.chunk_ids,
            "file_hash": self.file_hash,
            "metadata": self.metadata,
            "error": self.error,
        }


def ingest_document(
    file_path: str,
    override_metadata: Optional[Dict[str, Any]] = None,
    reindex: bool = False,
) -> IngestionResult:
    """
    Full ingestion pipeline for a single document.

    Steps:
    1. Extract metadata and file hash
    2. Check for duplicates (by file hash)
    3. Load document pages
    4. Enrich with metadata
    5. Chunk text
    6. Index in ChromaDB
    7. Move to processed/ directory

    Args:
        file_path: Absolute path to the document
        override_metadata: Admin-supplied metadata (name, version, etc.)
        reindex: If True, delete existing chunks and re-index

    Returns:
        IngestionResult with success status and chunk count
    """
    result = IngestionResult()
    path = Path(file_path)

    if not path.exists():
        result.error = f"File not found: {file_path}"
        logger.error("ingest_file_not_found", path=file_path)
        return result

    # Validate extension
    ext = path.suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions_set:
        result.error = f"Unsupported file type: {ext}"
        _move_to_rejected(path, result.error)
        return result

    # Validate size
    if path.stat().st_size > settings.max_upload_size_bytes:
        result.error = f"File too large: {path.stat().st_size} bytes (max {settings.max_upload_size_bytes})"
        _move_to_rejected(path, result.error)
        return result

    try:
        # Step 1: Extract metadata
        base_metadata = extract_metadata(str(path), override=override_metadata)
        result.file_hash = base_metadata["file_hash"]
        result.metadata = base_metadata

        # Step 2: Handle reindex (delete existing chunks)
        if reindex:
            logger.info("reindex_triggered", source_file=path.name)
            vectorstore.delete_by_source_file(path.name)

        # Step 3: Load pages
        logger.info("ingestion_loading", source_file=path.name)
        raw_docs = load_document(str(path))

        if not raw_docs:
            result.error = "Document produced no text content (possibly scanned/image PDF)"
            _move_to_rejected(path, result.error)
            return result

        # Step 4: Enrich with metadata
        enriched_docs = enrich_document_metadata(raw_docs, base_metadata)

        # Step 5: Chunk
        chunker = get_chunker("recursive")
        chunks = chunker.split(enriched_docs)

        if not chunks:
            result.error = "Chunking produced no output"
            _move_to_rejected(path, result.error)
            return result

        # Step 6: Index
        logger.info("ingestion_indexing", chunks=len(chunks), source_file=path.name)
        ids = vectorstore.add_documents(chunks)

        # Step 7: Move to processed
        _move_to_processed(path)

        result.success = True
        result.chunk_count = len(chunks)
        result.chunk_ids = ids
        logger.info(
            "ingestion_complete",
            source_file=path.name,
            chunks=len(chunks),
            document_name=base_metadata.get("document_name"),
        )

    except Exception as exc:
        result.error = str(exc)
        logger.error("ingestion_failed", source_file=path.name, error=str(exc))
        _move_to_rejected(path, str(exc))

    return result


def ingest_directory(
    directory: str = None,
    reindex: bool = False,
) -> List[IngestionResult]:
    """Ingest all documents in a directory. Returns list of results."""
    dir_path = Path(directory or settings.documents_raw_dir)
    if not dir_path.exists():
        logger.warning("ingest_directory_not_found", path=str(dir_path))
        return []

    results = []
    for file_path in dir_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower().lstrip(".") in settings.allowed_extensions_set:
            result = ingest_document(str(file_path), reindex=reindex)
            results.append(result)

    success = sum(1 for r in results if r.success)
    failed = len(results) - success
    logger.info("batch_ingestion_complete", total=len(results), success=success, failed=failed)
    return results


def _move_to_processed(path: Path) -> None:
    dest_dir = Path(settings.documents_processed_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if not dest.exists():
        shutil.copy2(str(path), str(dest))


def _move_to_rejected(path: Path, reason: str) -> None:
    dest_dir = Path(settings.documents_rejected_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if not dest.exists():
        shutil.copy2(str(path), str(dest))
    # Write rejection reason
    (dest_dir / f"{path.stem}_rejection_reason.txt").write_text(reason, encoding="utf-8")
    logger.warning("document_rejected", source_file=path.name, reason=reason)
