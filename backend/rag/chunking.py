"""
PolicyPilot — Text Chunking
Factory pattern allows swapping RecursiveCharacterTextSplitter
for semantic chunking without touching ingestion pipeline.
"""
from __future__ import annotations

import uuid
from typing import List, Literal

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()

ChunkerType = Literal["recursive", "semantic"]  # semantic: TODO Phase 2+


class RecursiveChunker:
    """
    Default chunker using RecursiveCharacterTextSplitter.
    Preserves page-level metadata while creating smaller, overlapping chunks.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )

    def split(self, docs: List[Document]) -> List[Document]:
        chunks = self._splitter.split_documents(docs)
        # Assign unique chunk IDs and chunk index per page
        for idx, chunk in enumerate(chunks):
            doc_name = chunk.metadata.get("document_name", "doc")
            version = chunk.metadata.get("version", "1")
            page = chunk.metadata.get("page", 0)
            slug = doc_name.lower().replace(" ", "-")[:30]
            chunk.metadata["chunk_id"] = f"{slug}-v{version}-p{page}-c{idx}"
            chunk.metadata["chunk_index"] = idx
        logger.info("chunks_created", count=len(chunks))
        return chunks


class SemanticChunker:
    """
    TODO: Implement semantic chunking in Phase 2+.
    Uses embedding similarity to find natural split points.
    This stub raises NotImplementedError to make the gap explicit.
    """

    def split(self, docs: List[Document]) -> List[Document]:
        raise NotImplementedError(
            "SemanticChunker is not yet implemented. "
            "Use RecursiveChunker or configure CHUNKER_TYPE=recursive."
        )


def get_chunker(chunker_type: ChunkerType = "recursive") -> RecursiveChunker:
    """Factory: return the configured chunker."""
    if chunker_type == "recursive":
        return RecursiveChunker()
    elif chunker_type == "semantic":
        return SemanticChunker()  # type: ignore
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")
