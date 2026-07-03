"""ConText Top-Level Engine.

High-Level API:
    >>> ctx = ConText()
    >>> ctx.build("./docs")
    >>> answer = ctx.query("What is X?")
    >>> print(answer.text)
    >>> for s in answer.sources:
    ...     print(s)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from context_engineer.core.budget import BudgetConfig
from context_engineer.core.chunker import select_chunker
from context_engineer.core.embedder import Embedder
from context_engineer.core.generator import Generator
from context_engineer.core.hybrid import HybridRetriever
from context_engineer.core.retriever import Retriever
from context_engineer.store.db import Chunk, Document, Store
from context_engineer.utils.tokens import count_tokens


# ─── Result Data Classes ───

@dataclass
class Source:
    """Eine zitierte Quelle in einer Antwort."""
    chunk_id: int
    text: str
    score: float
    source_path: str
    source_type: str
    chunk_index: int
    strategy: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "score": round(self.score, 4),
            "source_path": self.source_path,
            "source_type": self.source_type,
            "chunk_index": self.chunk_index,
            "strategy": self.strategy,
            "text_preview": self.text[:200] + ("..." if len(self.text) > 200 else ""),
        }


@dataclass
class Answer:
    """Antwort auf eine Query."""
    text: str
    sources: list[Source] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    query: str = ""
    model: str = ""

    def __str__(self) -> str:
        out = self.text
        if self.sources:
            out += "\n\nSources:"
            for i, s in enumerate(self.sources, start=1):
                out += f"\n  [{i}] {s.source_path} (score: {s.score:.3f})"
        return out


# ─── Engine ───

class ConText:
    """Top-level API für ConText."""

    def __init__(
        self,
        db_path: str | Path = ".context/store.db",
        llm_model: str = "llama3.2",
        embed_model: str = "nomic-embed-text",
        ollama_url: str = "http://localhost:11434",
        context_window: int = 8192,
        hybrid: bool = True,
    ):
        self.store = Store(db_path)
        self.embedder = Embedder(model=embed_model, base_url=ollama_url)
        self.budget = BudgetConfig(total_tokens=context_window)
        self.generator = Generator(model=llm_model, base_url=ollama_url, budget=self.budget)
        if hybrid:
            self.retriever = HybridRetriever(self.store, self.embedder, self.budget)
        else:
            self.retriever = Retriever(self.store, self.embedder, self.budget)
        self.hybrid = hybrid

    # ─── Build / Index ───

    def build(
        self,
        path: str | Path,
        recursive: bool = True,
        pattern: str = "*.{md,txt,py,js,ts,go,rs,java,c,cpp,h,hpp,json,yaml,yml}",
        max_file_size_mb: float = 5.0,
    ) -> dict:
        """Indexiere alle Dateien unter path.

        Returns:
            {"files": N, "chunks": M, "skipped": K}
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        # Collect files
        if path.is_file():
            files = [path]
        else:
            files = []
            for ext in pattern.replace("{", "").replace("}", "").split(","):
                ext = ext.strip().lstrip("*")
                if recursive:
                    files.extend(path.rglob(f"*{ext}"))
                else:
                    files.extend(path.glob(f"*{ext}"))
            files = sorted(set(files))
        # Filter size
        max_bytes = int(max_file_size_mb * 1024 * 1024)
        files = [f for f in files if f.stat().st_size <= max_bytes]
        stats = {"files": 0, "chunks": 0, "skipped": 0}
        for file in files:
            try:
                content = self._read_file(file)
                if not content.strip():
                    stats["skipped"] += 1
                    continue
                doc = self.store.add_document(
                    source_path=str(file),
                    content=content,
                    source_type="file",
                )
                # Check if chunks already exist for this doc
                if doc.id is not None:
                    existing = self.store.get_chunks_for_document(doc.id)
                else:
                    existing = []
                if existing:
                    stats["skipped"] += 1
                    continue
                # Chunk
                chunker = select_chunker(str(file), content)
                raw_chunks = chunker.chunk(content)
                # Store chunks
                if doc.id is None:
                    continue
                db_chunks = [
                    Chunk(
                        id=None,
                        document_id=doc.id,
                        chunk_index=i,
                        text=c.text,
                        token_count=c.token_count,
                        char_count=c.char_count,
                        strategy=c.strategy,
                        metadata={"source": str(file), "type": "file"},
                    )
                    for i, c in enumerate(raw_chunks)
                ]
                chunk_ids = self.store.add_chunks(db_chunks)
                # Embed
                texts = [c.text for c in raw_chunks]
                vectors = self.embedder.embed_batch(texts)
                for cid, vec in zip(chunk_ids, vectors):
                    self.store.add_embedding(cid, vec, self.embedder.model)
                stats["files"] += 1
                stats["chunks"] += len(chunk_ids)
            except Exception as e:
                stats["skipped"] += 1
                # Log but continue
                print(f"  ! Skipped {file}: {e}")
        return stats

    def add_text(
        self,
        text: str,
        source: str = "manual",
        source_type: str = "paste",
    ) -> int:
        """Füge Rohtext direkt hinzu. Returns document_id."""
        doc = self.store.add_document(
            source_path=source,
            content=text,
            source_type=source_type,
        )
        if doc.id is None:
            raise RuntimeError("Failed to create document")
        chunker = select_chunker(source, text)
        raw_chunks = chunker.chunk(text)
        db_chunks = [
            Chunk(
                id=None,
                document_id=doc.id,
                chunk_index=i,
                text=c.text,
                token_count=c.token_count,
                char_count=c.char_count,
                strategy=c.strategy,
                metadata={"source": source, "type": source_type},
            )
            for i, c in enumerate(raw_chunks)
        ]
        chunk_ids = self.store.add_chunks(db_chunks)
        texts = [c.text for c in raw_chunks]
        vectors = self.embedder.embed_batch(texts)
        for cid, vec in zip(chunk_ids, vectors):
            self.store.add_embedding(cid, vec, self.embedder.model)
        return doc.id

    # ─── Query ───

    def query(
        self,
        question: str,
        top_k: int = 20,
        temperature: float = 0.3,
    ) -> Answer:
        """Stelle eine Frage, erhalte Antwort mit Quellen."""
        # Retrieve
        chunks = self.retriever.retrieve(question, top_k=top_k)
        # Build sources
        sources = []
        for c in chunks:
            doc = self.store.get_document(c.document_id)
            sources.append(Source(
                chunk_id=c.id or 0,
                text=c.text,
                score=c.score,
                source_path=doc.source_path if doc else "?",
                source_type=doc.source_type if doc else "?",
                chunk_index=c.chunk_index,
                strategy=c.strategy,
            ))
        # Generate
        if not chunks or self.store.count_chunks() == 0:
            return Answer(
                text="No documents indexed yet. Run `context build <path>` first to add documents.",
                sources=[],
                query=question,
                model=self.generator.model,
            )
        result = self.generator.generate(question, chunks, temperature=temperature)
        # Log
        self.store.log_query(
            query_text=question,
            response_text=result["text"],
            retrieved_chunk_ids=[c.id for c in chunks if c.id is not None],
            token_usage={
                "prompt": result["prompt_tokens"],
                "completion": result["completion_tokens"],
            },
            latency_ms=result["latency_ms"],
            model=self.generator.model,
        )
        return Answer(
            text=result["text"],
            sources=sources,
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            latency_ms=result["latency_ms"],
            query=question,
            model=self.generator.model,
        )

    # ─── Stats / List / Remove ───

    def stats(self) -> dict:
        s = self.store.stats()
        s["embedder"] = self.embedder.cache_info()
        s["llm_model"] = self.generator.model
        s["embed_model"] = self.embedder.model
        s["context_window"] = self.budget.total_tokens
        return s

    def list_documents(self) -> list[dict]:
        return [
            {
                "id": d.id,
                "source": d.source_path,
                "type": d.source_type,
                "created": d.metadata.get("created", ""),
            }
            for d in self.store.list_documents()
        ]

    def remove(self, source_path: str) -> int:
        return self.store.remove_document(source_path)

    # ─── Helpers ───

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")
