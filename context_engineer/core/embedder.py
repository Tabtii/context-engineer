"""Ollama Embedding-Client.

Ollama bietet /api/embeddings für Embedding-Modelle wie nomic-embed-text.
Wir nutzen requests (kein ollama-python Package — zero-dep).
"""

from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np
import requests


DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_BASE_URL = "http://localhost:11434"


class Embedder:
    """Client für Ollama Embeddings mit In-Memory Cache."""

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        cache_size: int = 10_000,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._cache: dict[str, np.ndarray] = {}
        self._cache_size = cache_size

    def embed(self, text: str) -> np.ndarray:
        """Hole Embedding für Text (mit Cache)."""
        text = text.strip()
        if not text:
            return np.zeros(self.dim(), dtype=np.float32)
        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
        vec = self._fetch(text)
        if len(self._cache) >= self._cache_size:
            # Evict oldest (FIFO)
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[cache_key] = vec
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed mehrere Texte. Nutzt Ollama's batch-endpunkt wenn verfügbar."""
        results = []
        to_fetch = []
        idx_map = []
        for i, t in enumerate(texts):
            t = t.strip()
            if not t:
                results.append(np.zeros(self.dim(), dtype=np.float32))
                continue
            key = self._cache_key(t)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append(None)  # placeholder
                to_fetch.append(t)
                idx_map.append(i)
        # Fetch missing in parallel (sequential for simplicity, but could use ThreadPool)
        for j, t in enumerate(to_fetch):
            vec = self._fetch(t)
            i = idx_map[j]
            results[i] = vec
            if len(self._cache) >= self._cache_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[self._cache_key(t)] = vec
        return results

    def _fetch(self, text: str) -> np.ndarray:
        url = f"{self.base_url}/api/embeddings"
        try:
            resp = requests.post(
                url,
                json={"model": self.model, "prompt": text},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return np.array(data["embedding"], dtype=np.float32)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to fetch embedding from Ollama at {url}. "
                f"Is Ollama running? Try: ollama pull {self.model}. Error: {e}"
            ) from e

    def dim(self) -> int:
        """Embedding-Dimension für das aktuelle Modell."""
        # Cache known dimensions
        known = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
            "snowflake-arctic-embed": 1024,
        }
        if self.model in known:
            return known[self.model]
        # Fallback: fetch one
        v = self.embed("test")
        return len(v)

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def clear_cache(self):
        self._cache.clear()

    def cache_info(self) -> dict:
        return {
            "size": len(self._cache),
            "max": self._cache_size,
            "model": self.model,
        }
