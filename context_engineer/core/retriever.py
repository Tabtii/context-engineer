"""Retriever: Vektor-Suche + Token-Budget-Awareness.

Nutzt Cosine-Similarity zwischen Query-Embedding und allen Chunk-Embeddings.
"""

from __future__ import annotations

import numpy as np

from context_engineer.core.budget import BudgetConfig, fit_to_budget
from context_engineer.core.embedder import Embedder
from context_engineer.store.db import Chunk, Store
from context_engineer.utils.tokens import count_tokens


class Retriever:
    """Top-K Cosine-Similarity Retrieval mit Token-Budget."""

    def __init__(
        self,
        store: Store,
        embedder: Embedder,
        budget: BudgetConfig | None = None,
    ):
        self.store = store
        self.embedder = embedder
        self.budget = budget or BudgetConfig()

    def retrieve(self, query: str, top_k: int = 20) -> list[Chunk]:
        """Finde die relevantesten Chunks für die Query."""
        # 0. Check ob überhaupt Chunks da sind (vermeidet Ollama-Calls)
        if self.store.count_chunks() == 0:
            return []
        # 1. Query-Embedding
        query_vec = self.embedder.embed(query)
        if query_vec.size == 0:
            return []
        # 2. Alle Embeddings laden
        matrix, chunk_ids = self.store.get_all_embeddings(model=self.embedder.model)
        if matrix.size == 0 or len(chunk_ids) == 0:
            return []
        # 3. Cosine-Similarity
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        scores = matrix_norm @ query_norm
        # 4. Top-K
        top_idx = np.argsort(-scores)[:top_k]
        candidates: list[tuple[str, float, int]] = []
        candidate_ids: list[int] = []
        for idx in top_idx:
            chunk = self.store.get_chunk(int(chunk_ids[int(idx)]))
            if not chunk:
                continue
            chunk.score = float(scores[int(idx)])
            candidates.append((chunk.text, chunk.score, chunk.token_count))
            candidate_ids.append(chunk.id)
        # 5. Token-Budget anwenden
        selected = fit_to_budget(candidates, self.budget.available)
        selected_ids = set()
        # Map selected texts back to chunks
        result = []
        # We need to re-iterate in order
        result_chunks: list[Chunk] = []
        for cid, (text, score, _) in zip(candidate_ids, candidates):
            chunk = self.store.get_chunk(cid)
            if chunk is None:
                continue
            chunk.score = score
            result_chunks.append(chunk)
        # Re-fit selection by ID
        for cid in candidate_ids:
            for rc in result_chunks:
                if rc.id == cid:
                    result.append(rc)
                    break
        # Apply budget by score
        final = []
        used = 0
        for c in result:
            if used + c.token_count <= self.budget.available:
                final.append(c)
                used += c.token_count
        return final

    def score_all(self, query: str) -> list[tuple[Chunk, float]]:
        """Gebe ALLE Chunks mit Score zurück (für Reranking etc)."""
        query_vec = self.embedder.embed(query)
        if query_vec.size == 0:
            return []
        matrix, chunk_ids = self.store.get_all_embeddings(model=self.embedder.model)
        if matrix.size == 0:
            return []
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        scores = matrix_norm @ query_norm
        out = []
        for i, cid in enumerate(chunk_ids):
            if cid is None:
                continue
            chunk = self.store.get_chunk(cid)
            if chunk:
                chunk.score = float(scores[i])
                out.append((chunk, float(scores[i])))
        return sorted(out, key=lambda x: x[1], reverse=True)
