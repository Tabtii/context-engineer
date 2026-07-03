"""BM25 Keyword-basierte Suche für Hybrid-Retrieval.

BM25 (Best Matching 25) ist der Standard-Algorithmus für Keyword-basierte
Suche. Wir kombinieren ihn mit Cosine-Similarity für Hybrid-Search.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from context_engineer.store.db import Chunk


# ─── Tokenizer ───

def tokenize(text: str) -> list[str]:
    """Einfache Tokenizer: lowercase, split auf non-alphanumeric, drop short tokens."""
    text = text.lower()
    tokens = re.findall(r"\b[a-z0-9_]{2,}\b", text)
    return tokens


# ─── BM25 Index ───

class BM25Index:
    """BM25 Index über alle Chunks.

    Wir bauen den Index einmal beim Start und updaten bei neuen Chunks.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunk_ids: list[int] = []
        self.docs: list[list[str]] = []  # tokenized chunks
        self.doc_lens: list[int] = []
        self.avgdl: float = 0.0
        self.df: Counter = Counter()  # document frequency per term
        self.idf: dict[str, float] = {}

    def fit(self, chunks: list[Chunk]):
        """Baue Index über alle Chunks."""
        self.chunk_ids = []
        self.docs = []
        self.doc_lens = []
        self.df = Counter()
        for chunk in chunks:
            tokens = tokenize(chunk.text)
            self.chunk_ids.append(chunk.id or 0)
            self.docs.append(tokens)
            self.doc_lens.append(len(tokens))
            # Document frequency
            for term in set(tokens):
                self.df[term] += 1
        # Average doc length
        n = max(1, len(self.docs))
        self.avgdl = sum(self.doc_lens) / n
        # IDF
        self.idf = {}
        for term, df in self.df.items():
            # Smoothed IDF
            self.idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[float]:
        """Berechne BM25-Score für alle Chunks."""
        if not self.docs or self.avgdl == 0:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = []
        for tokens, doc_len in zip(self.docs, self.doc_lens):
            score = 0.0
            tf = Counter(tokens)
            for qt in query_tokens:
                if qt not in tf:
                    continue
                idf = self.idf.get(qt, 0.0)
                tf_norm = (tf[qt] * (self.k1 + 1)) / (
                    tf[qt] + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                )
                score += idf * tf_norm
            scores.append(score)
        return scores

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Return top-k (chunk_id, score) Tupel."""
        scores = self.score(query)
        if not scores:
            return []
        indexed = list(zip(self.chunk_ids, scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:top_k]
