"""Hybrid Retriever: Vector + BM25 mit Reciprocal Rank Fusion.

RRF ist die Standard-Methode um zwei Rankings zu kombinieren:
  RRF_score(doc) = sum( 1 / (k + rank_i) ) für jedes Ranking i

K=60 ist die übliche Konstante.
"""

from __future__ import annotations

import numpy as np

from context_engineer.core.bm25 import BM25Index, tokenize
from context_engineer.core.budget import BudgetConfig, fit_to_budget
from context_engineer.core.embedder import Embedder
from context_engineer.store.db import Chunk, Store
from context_engineer.utils.tokens import count_tokens


RRF_K = 60


class HybridRetriever:
    """Kombiniert Vector- und BM25-Retrieval mit Reciprocal Rank Fusion."""

    def __init__(
        self,
        store: Store,
        embedder: Embedder,
        budget: BudgetConfig | None = None,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ):
        self.store = store
        self.embedder = embedder
        self.budget = budget or BudgetConfig()
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self._bm25: BM25Index | None = None
        self._chunk_count = 0

    def _ensure_bm25(self):
        """Lazy BM25 index build."""
        n = self.store.count_chunks()
        if self._bm25 is None or self._chunk_count != n:
            chunks = self._load_all_chunks()
            self._bm25 = BM25Index()
            self._bm25.fit(chunks)
            self._chunk_count = n

    def _load_all_chunks(self) -> list[Chunk]:
        """Lade alle Chunks aus dem Store."""
        matrix, chunk_ids = self.store.get_all_embeddings(model=self.embedder.model)
        chunks = []
        for cid in chunk_ids:
            if cid is None:
                continue
            c = self.store.get_chunk(cid)
            if c:
                chunks.append(c)
        return chunks

    def retrieve(self, query: str, top_k: int = 20) -> list[Chunk]:
        """Hybrid-Retrieval: RRF-Fusion von Vector + BM25."""
        if self.store.count_chunks() == 0:
            return []
        # 1. Vector retrieval
        vec_results = self._vector_search(query, top_k=top_k * 2)
        # 2. BM25 retrieval
        self._ensure_bm25()
        bm25_results = self._bm25.search(query, top_k=top_k * 2) if self._bm25 else []
        # 3. RRF Fusion
        fused = self._rrf_fuse(vec_results, bm25_results)
        # 4. Top-K nach RRF
        top = fused[:top_k]
        # 5. Token-Budget anwenden
        return self._apply_budget(top, query)

    def _vector_search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        """Cosine-Similarity Vector Search."""
        query_vec = self.embedder.embed(query)
        if query_vec.size == 0:
            return []
        matrix, chunk_ids = self.store.get_all_embeddings(model=self.embedder.model)
        if matrix.size == 0:
            return []
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        scores = matrix_norm @ query_norm
        indexed = []
        for i, cid in enumerate(chunk_ids):
            if cid is None:
                continue
            chunk = self.store.get_chunk(cid)
            if chunk:
                indexed.append((chunk, float(scores[i])))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:top_k]

    def _rrf_fuse(
        self,
        vec_results: list[tuple[Chunk, float]],
        bm25_results: list[tuple[int, float]],
    ) -> list[tuple[Chunk, float]]:
        """Reciprocal Rank Fusion."""
        scores: dict[int, float] = {}
        chunk_map: dict[int, Chunk] = {}
        # Vector
        for rank, (chunk, _score) in enumerate(vec_results):
            cid = chunk.id or 0
            scores[cid] = scores.get(cid, 0.0) + self.vector_weight / (RRF_K + rank + 1)
            chunk_map[cid] = chunk
        # BM25
        for rank, (cid, _score) in enumerate(bm25_results):
            scores[cid] = scores.get(cid, 0.0) + self.bm25_weight / (RRF_K + rank + 1)
            if cid not in chunk_map:
                chunk = self.store.get_chunk(cid)
                if chunk:
                    chunk_map[cid] = chunk
        # Sort by fused score
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        out = []
        for cid, rrf_score in sorted_results:
            if cid in chunk_map:
                chunk = chunk_map[cid]
                chunk.score = rrf_score
                out.append((chunk, rrf_score))
        return out

    def _apply_budget(self, results: list[tuple[Chunk, float]], query: str) -> list[Chunk]:
        """Token-Budget anwenden."""
        items = [(c.text, c.score, c.token_count) for c, _ in results]
        selected = fit_to_budget(items, self.budget.available)
        # Map back to chunks
        selected_texts = {s[0] for s in selected}
        return [c for c, _ in results if c.text in selected_texts]


def tokenize_for_test(text: str) -> list[str]:
    """Re-export für Tests."""
    return tokenize(text)
