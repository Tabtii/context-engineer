"""Tests for ConText."""

import os
import tempfile
from pathlib import Path

import pytest

from context_engineer import ConText, Source, Answer
from context_engineer.core.chunker import (
    FixedChunker, SemanticChunker, SlidingChunker,
    MarkdownChunker, CodeChunker, select_chunker,
)
from context_engineer.core.budget import BudgetConfig, fit_to_budget
from context_engineer.utils.tokens import count_tokens, truncate_to_tokens


# ─── Tokens ───

def test_count_tokens_basic():
    assert count_tokens("") == 0
    assert count_tokens("hello") > 0
    assert count_tokens("hello world") >= 2


def test_count_tokens_longer():
    text = "The quick brown fox jumps over the lazy dog. " * 10
    tokens = count_tokens(text)
    # Should be roughly proportional
    assert tokens > 50
    assert tokens < 200


def test_truncate_to_tokens():
    text = "This is a test. " * 100
    truncated = truncate_to_tokens(text, max_tokens=20)
    assert count_tokens(truncated) <= 25  # allow some overhead for "..."
    assert len(truncated) < len(text)


# ─── Budget ───

def test_budget_config():
    b = BudgetConfig(total_tokens=8192)
    assert b.available == 8192 - 1024 - 256 - 100


def test_fit_to_budget_empty():
    result = fit_to_budget([], 1000)
    assert result == []


def test_fit_to_budget_simple():
    items = [("a", 0.9, 100), ("b", 0.8, 200), ("c", 0.7, 800)]
    result = fit_to_budget(items, 500)
    # Should pick "a" (100) and "b" (200) = 300. "c" would be 800, exceeds 500.
    assert len(result) == 2
    assert result[0][0] == "a"  # highest score first
    assert result[1][0] == "b"


def test_fit_to_budget_all_fit():
    items = [("a", 0.9, 100), ("b", 0.8, 200)]
    result = fit_to_budget(items, 1000)
    assert len(result) == 2


def test_fit_to_budget_none_fit():
    items = [("a", 0.9, 2000)]
    result = fit_to_budget(items, 100)
    assert len(result) == 0


# ─── Chunkers ───

def test_fixed_chunker():
    text = "x" * 3000
    chunker = FixedChunker(chunk_size=1000, overlap=200)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 3
    assert all(c.strategy == "fixed" for c in chunks)
    assert all(c.char_count > 0 for c in chunks)


def test_fixed_chunker_empty():
    chunker = FixedChunker()
    assert chunker.chunk("") == []


def test_semantic_chunker():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunker = SemanticChunker(max_tokens=10, min_tokens=2)
    chunks = chunker.chunk(text)
    assert len(chunks) > 0
    assert all(c.strategy == "semantic" for c in chunks)


def test_sliding_chunker():
    text = "a" * 5000
    chunker = SlidingChunker(chunk_size=1000, overlap_ratio=0.3)
    chunks = chunker.chunk(text)
    assert len(chunks) > 3
    # Overlap should be 300
    assert all(c.metadata.get("overlap") == 300 for c in chunks)


def test_markdown_chunker():
    text = """# Header 1
Content 1
## Header 2
Content 2
### Header 3
Content 3"""
    chunker = MarkdownChunker(max_tokens=100)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    assert all(c.strategy == "markdown" for c in chunks)


def test_code_chunker_python():
    text = '''
def foo():
    return 1

def bar():
    return 2

class MyClass:
    def method(self):
        return 3

def baz():
    return 4
'''
    chunker = CodeChunker(max_tokens=100)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    assert all(c.strategy == "code" for c in chunks)


def test_select_chunker_auto():
    # Python file
    c = select_chunker("test.py", "def foo(): pass")
    assert isinstance(c, CodeChunker)
    # Markdown file
    c = select_chunker("test.md", "# Header")
    assert isinstance(c, MarkdownChunker)
    # Plain text
    c = select_chunker("test.txt", "Some text")
    assert isinstance(c, SemanticChunker)


# ─── Store ───

def test_store_init():
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "test.db"
        from context_engineer.store.db import Store
        store = Store(store_path)
        assert store_path.exists()
        stats = store.stats()
        assert stats["documents"] == 0
        assert stats["chunks"] == 0


def test_store_add_document():
    with tempfile.TemporaryDirectory() as tmp:
        from context_engineer.store.db import Store
        store = Store(Path(tmp) / "test.db")
        doc = store.add_document("test.md", "Hello world", "file")
        assert doc.id is not None
        assert doc.content_hash is not None
        # Adding same content returns same doc
        doc2 = store.add_document("test.md", "Hello world", "file")
        assert doc.id == doc2.id


def test_store_chunks():
    with tempfile.TemporaryDirectory() as tmp:
        from context_engineer.store.db import Store, Chunk
        store = Store(Path(tmp) / "test.db")
        doc = store.add_document("test.md", "Hello", "file")
        chunks = [
            Chunk(
                id=None,
                document_id=doc.id,
                chunk_index=i,
                text=f"Chunk {i}",
                token_count=10,
                char_count=20,
                strategy="fixed",
                metadata={},
            )
            for i in range(3)
        ]
        ids = store.add_chunks(chunks)
        assert len(ids) == 3
        all_chunks = store.get_chunks_for_document(doc.id)
        assert len(all_chunks) == 3


# ─── Engine (no Ollama) ───

def test_engine_init():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        engine = ConText(db_path=db, llm_model="fake", embed_model="fake")
        stats = engine.stats()
        assert stats["documents"] == 0
        assert stats["chunks"] == 0


def test_engine_query_empty():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        engine = ConText(db_path=db, llm_model="fake", embed_model="fake")
        answer = engine.query("What?")
        # With no documents, should return early message (not crash)
        assert "No documents indexed" in answer.text or "build" in answer.text
        assert answer.sources == []


# ─── Integration (requires Ollama) ───

@pytest.mark.skipif(
    not os.path.exists("/tmp/ollama-test"),
    reason="Ollama integration test only runs in test env",
)
def test_ollama_embed():
    """Integration test with real Ollama."""
    from context_engineer.core.embedder import Embedder
    emb = Embedder(model="nomic-embed-text")
    vec = emb.embed("Hello world")
    assert vec.shape[0] == 768  # nomic-embed-text dim
    # Cache hit
    vec2 = emb.embed("Hello world")
    assert vec.shape == vec2.shape
