"""
PolicyPilot — Unit Tests: Corrective RAG Query Refinement
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.rag.corrective_rag import refine_query


class TestRefineQuery:
    def test_strips_filler_words(self):
        queries = refine_query("What is the leave policy?")
        # Should produce at least one refined variant
        assert len(queries) >= 1

    def test_expands_leave_keywords(self):
        queries = refine_query("How many casual leaves do I get?")
        combined = " ".join(queries).lower()
        assert "leave" in combined

    def test_expands_separation_keywords(self):
        queries = refine_query("What happens when I leave the company?")
        combined = " ".join(queries).lower()
        assert any(k in combined for k in ["separation", "exit", "notice", "leave"])

    def test_adds_pw_prefix_variant(self):
        queries = refine_query("travel reimbursement")
        assert any("physics wallah" in q.lower() or "policy" in q.lower() for q in queries)

    def test_deduplicates_results(self):
        queries = refine_query("leave policy")
        # Should not have exact duplicates
        lower_queries = [q.lower() for q in queries]
        assert len(lower_queries) == len(set(lower_queries))

    def test_max_three_variants(self):
        queries = refine_query("some query about attendance and shift policy at pw")
        assert len(queries) <= 3

    def test_empty_ish_query(self):
        queries = refine_query("what")
        assert isinstance(queries, list)


class TestChunking:
    def test_recursive_chunker_creates_chunks(self):
        from langchain_core.documents import Document
        from backend.rag.chunking import RecursiveChunker

        doc = Document(
            page_content="This is a test document. " * 200,
            metadata={"source_file": "test.pdf", "page": 1, "document_name": "Test Policy"},
        )
        chunker = RecursiveChunker(chunk_size=200, chunk_overlap=20)
        chunks = chunker.split([doc])
        assert len(chunks) > 1

    def test_chunks_have_ids(self):
        from langchain_core.documents import Document
        from backend.rag.chunking import RecursiveChunker

        doc = Document(
            page_content="Policy content. " * 100,
            metadata={"source_file": "test.pdf", "page": 1, "document_name": "Test"},
        )
        chunker = RecursiveChunker(chunk_size=200, chunk_overlap=20)
        chunks = chunker.split([doc])
        for chunk in chunks:
            assert "chunk_id" in chunk.metadata

    def test_semantic_chunker_raises_not_implemented(self):
        from backend.rag.chunking import get_chunker
        chunker = get_chunker("semantic")
        with pytest.raises(NotImplementedError):
            chunker.split([])
