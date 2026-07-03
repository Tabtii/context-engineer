"""Token-Counter mit tiktoken + Ollama-fallback.

Tiktoken ist der Gold-Standard für OpenAI-Modelle, aber für lokale Modelle
müssen wir approximieren. Wir nutzen die `tiktoken` Library mit `cl100k_base`
als Default — das ist gut genug für die meisten Open-Source-Modelle.
"""

from __future__ import annotations

import re
from functools import lru_cache

try:
    import tiktoken
    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False


# Approximation: 1 Token ≈ 4 Zeichen für Englisch/Code, ~2 Zeichen für Deutsch
# Wir nutzen tiktoken wenn verfügbar, sonst chars/4.
_CHARS_PER_TOKEN = 4.0


@lru_cache(maxsize=1)
def _get_encoder(model: str = "cl100k_base"):
    """Cache den tiktoken Encoder."""
    if not _HAS_TIKTOKEN:
        return None
    try:
        return tiktoken.get_encoding(model)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Zähle Tokens im Text.

    Args:
        text: Input-Text
        model: tiktoken Encoding-Name (default: cl100k_base)

    Returns:
        Token-Count (approx)
    """
    if not text:
        return 0
    enc = _get_encoder(model)
    if enc is not None:
        return len(enc.encode(text))
    # Fallback: chars/4 approximation
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def truncate_to_tokens(text: str, max_tokens: int, model: str = "cl100k_base") -> str:
    """Kürze Text auf max_tokens Tokens.

    Versucht an Wortgrenzen zu schneiden.
    """
    if count_tokens(text, model) <= max_tokens:
        return text
    enc = _get_encoder(model)
    if enc is None:
        # Approximation
        chars = int(max_tokens * _CHARS_PER_TOKEN)
        return text[:chars].rsplit(" ", 1)[0] + "..."
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = enc.decode(tokens[:max_tokens])
    # Versuche am Satzende zu schneiden
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_period > len(truncated) * 0.7:
        truncated = truncated[: last_period + 1]
    return truncated + "..."


def estimate_messages_tokens(messages: list[dict], model: str = "cl100k_base") -> int:
    """OpenAI-style: 4 Tokens pro Message-Overhead + Content.

    Format: [{"role": "user", "content": "..."}]
    """
    total = 0
    for msg in messages:
        total += 4  # role + overhead
        total += count_tokens(msg.get("content", ""), model)
    total += 2  # assistant primer
    return total
