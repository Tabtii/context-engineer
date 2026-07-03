"""SQLite Storage Layer mit Embedding-Cache.

Schema:
- documents: Quelldokumente
- chunks: Text-Segmente (mit Token-Count)
- embeddings: Vektor-Repräsentationen (BLOB)
- queries: Query-Log für Analytics

Wir nutzen SQLite ohne ORM — direkt mit sqlite3 für maximale Kontrolle.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

import numpy as np


# ─── Schema ───

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_type TEXT,
    content_hash TEXT UNIQUE NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    char_count INTEGER,
    strategy TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_strategy ON chunks(strategy);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    vector BLOB NOT NULL,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    response_text TEXT,
    retrieved_chunk_ids JSON,
    token_usage JSON,
    latency_ms INTEGER,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ─── Data classes ───

@dataclass
class Document:
    id: Optional[int]
    source_path: str
    source_type: str
    content_hash: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    id: Optional[int]
    document_id: int
    chunk_index: int
    text: str
    token_count: int
    char_count: int
    strategy: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0  # filled by retriever


# ─── Storage ───

class Store:
    """SQLite-basierter Storage mit Embedding-Cache."""

    def __init__(self, db_path: str | Path = ".context/store.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    # ─── Documents ───

    def add_document(
        self,
        source_path: str,
        content: str,
        source_type: str = "file",
        metadata: Optional[dict] = None,
    ) -> Document:
        """Füge ein Dokument hinzu (oder hole existierendes per content_hash)."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._conn() as conn:
            # Check ob schon vorhanden
            row = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if row:
                return Document(
                    id=row["id"],
                    source_path=row["source_path"],
                    source_type=row["source_type"],
                    content_hash=row["content_hash"],
                    metadata=json.loads(row["metadata"] or "{}"),
                )
            cur = conn.execute(
                """INSERT INTO documents (source_path, source_type, content_hash, metadata)
                   VALUES (?, ?, ?, ?)""",
                (source_path, source_type, content_hash, json.dumps(metadata or {})),
            )
            conn.commit()
            return Document(
                id=cur.lastrowid,
                source_path=source_path,
                source_type=source_type,
                content_hash=content_hash,
                metadata=metadata or {},
            )

    def get_document(self, doc_id: int) -> Optional[Document]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if not row:
                return None
            return Document(
                id=row["id"],
                source_path=row["source_path"],
                source_type=row["source_type"],
                content_hash=row["content_hash"],
                metadata=json.loads(row["metadata"] or "{}"),
            )

    def remove_document(self, source_path: str) -> int:
        """Entferne alle Chunks/Embeddings für source_path. Returns deleted count."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM documents WHERE source_path = ?", (source_path,)
            )
            conn.commit()
            return cur.rowcount

    def list_documents(self) -> list[Document]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
            return [
                Document(
                    id=r["id"],
                    source_path=r["source_path"],
                    source_type=r["source_type"],
                    content_hash=r["content_hash"],
                    metadata=json.loads(r["metadata"] or "{}"),
                )
                for r in rows
            ]

    # ─── Chunks ───

    def add_chunks(self, chunks: list[Chunk]) -> list[int]:
        """Bulk-Insert. Returns IDs in order."""
        if not chunks:
            return []
        with self._conn() as conn:
            ids = []
            for c in chunks:
                cur = conn.execute(
                    """INSERT INTO chunks
                       (document_id, chunk_index, text, token_count, char_count, strategy, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        c.document_id,
                        c.chunk_index,
                        c.text,
                        c.token_count,
                        c.char_count,
                        c.strategy,
                        json.dumps(c.metadata),
                    ),
                )
                ids.append(cur.lastrowid)
            conn.commit()
            return ids

    def get_chunks_for_document(self, document_id: int) -> list[Chunk]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM chunks WHERE document_id = ?
                   ORDER BY chunk_index ASC""",
                (document_id,),
            ).fetchall()
            return [self._row_to_chunk(r) for r in rows]

    def get_chunk(self, chunk_id: int) -> Optional[Chunk]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
            ).fetchone()
            return self._row_to_chunk(row) if row else None

    def count_chunks(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            token_count=row["token_count"],
            char_count=row["char_count"],
            strategy=row["strategy"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # ─── Embeddings ───

    def add_embedding(self, chunk_id: int, vector: np.ndarray, model: str):
        """Speichere Embedding als BLOB (float32 little-endian)."""
        if vector.dtype != np.float32:
            vector = vector.astype(np.float32)
        blob = vector.tobytes()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO embeddings (chunk_id, vector, model, dim)
                   VALUES (?, ?, ?, ?)""",
                (chunk_id, blob, model, len(vector)),
            )
            conn.commit()

    def get_all_embeddings(self, model: Optional[str] = None) -> tuple[np.ndarray, list[int]]:
        """Lade alle Embeddings. Returns (matrix [N, D], chunk_ids)."""
        with self._conn() as conn:
            if model:
                rows = conn.execute(
                    "SELECT chunk_id, vector, dim FROM embeddings WHERE model = ?",
                    (model,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT chunk_id, vector, dim FROM embeddings"
                ).fetchall()
            if not rows:
                return np.empty((0, 0), dtype=np.float32), []
            dim = rows[0]["dim"]
            matrix = np.empty((len(rows), dim), dtype=np.float32)
            ids = []
            for i, r in enumerate(rows):
                matrix[i] = np.frombuffer(r["vector"], dtype=np.float32)
                ids.append(r["chunk_id"])
            return matrix, ids

    def embedding_exists(self, chunk_id: int, model: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM embeddings WHERE chunk_id = ? AND model = ?",
                (chunk_id, model),
            ).fetchone()
            return row is not None

    # ─── Queries ───

    def log_query(
        self,
        query_text: str,
        response_text: str,
        retrieved_chunk_ids: list[int],
        token_usage: dict,
        latency_ms: int,
        model: str,
    ):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO queries
                   (query_text, response_text, retrieved_chunk_ids, token_usage, latency_ms, model)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    query_text,
                    response_text,
                    json.dumps(retrieved_chunk_ids),
                    json.dumps(token_usage),
                    latency_ms,
                    model,
                ),
            )
            conn.commit()

    # ─── Stats ───

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embeddings = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            queries = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
            strategies = conn.execute(
                "SELECT strategy, COUNT(*) as count FROM chunks GROUP BY strategy"
            ).fetchall()
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "documents": docs,
                "chunks": chunks,
                "embeddings": embeddings,
                "queries": queries,
                "strategies": {r["strategy"]: r["count"] for r in strategies},
                "db_size_mb": round(size_bytes / (1024 * 1024), 2),
                "db_path": str(self.db_path),
            }
