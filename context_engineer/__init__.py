"""ConText — Context-Engineer for AI Agents.

A zero-config RAG pipeline for local LLMs (Ollama) with automatic
context management, source citation, and token-budget awareness.

Example:
    >>> from context_engineer import ConText
    >>> ctx = ConText()
    >>> ctx.build("./docs")
    >>> answer = ctx.query("What is the main topic?")
    >>> print(answer.text)
    >>> print(answer.sources)  # [Source(...), Source(...)]

CLI:
    $ context build ./docs
    $ context query "What is the main topic?"
    $ context stats
"""

__version__ = "0.1.0"
__author__ = "Torben <torbi95@gmail.com>"

from context_engineer.core.engine import ConText, Source, Answer

__all__ = ["ConText", "Source", "Answer", "__version__"]
