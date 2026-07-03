"""Token-Budget-Manager.

Stellt sicher, dass die Summe der Token aller Chunks das verfügbare
Context-Budget nicht überschreitet. Priorisiert nach Score.
"""

from __future__ import annotations

from dataclasses import dataclass

from context_engineer.utils.tokens import count_tokens


@dataclass
class BudgetConfig:
    """Context-Window Konfiguration."""
    total_tokens: int = 8192        # Modell-Context-Window
    reserve_response: int = 1024    # Platz für LLM-Antwort
    reserve_system: int = 256       # System-Prompt
    reserve_citation: int = 100     # Quellen-Verweise

    @property
    def available(self) -> int:
        return max(
            256,
            self.total_tokens - self.reserve_response - self.reserve_system - self.reserve_citation,
        )


def fit_to_budget(
    items: list[tuple[str, float, int]],  # (text, score, tokens)
    budget: int,
) -> list[tuple[str, float, int]]:
    """Greedy-Fit: Höchster Score zuerst, bis Budget voll.

    Args:
        items: Liste von (text, score, token_count) Tupeln
        budget: Maximale Token-Summe

    Returns:
        Gefilterte Liste, sortiert nach Score (absteigend)
    """
    sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
    selected = []
    used = 0
    for text, score, tokens in sorted_items:
        if used + tokens <= budget:
            selected.append((text, score, tokens))
            used += tokens
    return selected
