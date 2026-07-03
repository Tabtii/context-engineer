"""Ollama LLM-Generator für RAG-Responses."""

from __future__ import annotations

import time
from typing import Optional

import requests

from context_engineer.core.budget import BudgetConfig
from context_engineer.store.db import Chunk
from context_engineer.utils.tokens import count_tokens, estimate_messages_tokens


DEFAULT_LLM_MODEL = "llama3.2"
DEFAULT_BASE_URL = "http://localhost:11434"

SYSTEM_PROMPT = """You are a helpful AI assistant. Answer the user's question based on the provided context.

Rules:
1. Use ONLY the information in the context below to answer. If the answer is not in the context, say "I don't have enough information."
2. Cite sources using [1], [2], [3] notation that matches the context labels.
3. Be concise and direct. No filler.
4. If the user asks in German, answer in German. Otherwise match the user's language.
5. Never invent facts not present in the context."""


class Generator:
    """Ollama LLM Client mit Source-Citation."""

    def __init__(
        self,
        model: str = DEFAULT_LLM_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        budget: BudgetConfig | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.budget = budget or BudgetConfig()

    def generate(
        self,
        query: str,
        chunks: list[Chunk],
        system_prompt: str = SYSTEM_PROMPT,
        temperature: float = 0.3,
    ) -> dict:
        """Generiere Antwort basierend auf Query + Chunks.

        Returns:
            {
                "text": str,
                "prompt_tokens": int,
                "completion_tokens": int,
                "latency_ms": int,
            }
        """
        # Build context with citations
        context_text = self._format_context(chunks)
        user_prompt = f"""Context:
{context_text}

Question: {query}

Answer:"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        start = time.time()
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": self.budget.reserve_response,
                    },
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["message"]["content"]
            # Ollama liefert Token-Counts in "eval_count" / "prompt_eval_count"
            prompt_tokens = data.get("prompt_eval_count", count_tokens(user_prompt + system_prompt))
            completion_tokens = data.get("eval_count", count_tokens(text))
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to generate from Ollama at {self.base_url}. "
                f"Is Ollama running? Try: ollama pull {self.model}. Error: {e}"
            ) from e
        latency_ms = int((time.time() - start) * 1000)
        return {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
        }

    @staticmethod
    def _format_context(chunks: list[Chunk]) -> str:
        """Formatiere Chunks mit [1], [2], ... Labels für Citation."""
        parts = []
        for i, c in enumerate(chunks, start=1):
            source = c.metadata.get("source", c.metadata.get("header", ""))
            header = f"--- Source [{i}]: {source} ---\n" if source else f"--- Source [{i}] ---\n"
            parts.append(header + c.text)
        return "\n\n".join(parts)
