"""5 Chunking-Strategien für verschiedene Inhalts-Typen.

1. fixed       — N Zeichen mit M Overlap
2. sliding     — Wie fixed, aber größerer Overlap
3. semantic    — Satzgrenzen respektieren
4. markdown    — MD-Struktur als Boundaries
5. code        — Source-Code Funktionen/Klassen
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from context_engineer.utils.tokens import count_tokens


@dataclass
class Chunk:
    text: str
    token_count: int
    char_count: int
    strategy: str
    metadata: dict


class Chunker(Protocol):
    def chunk(self, text: str) -> list[Chunk]: ...


# ─── Strategy 1: Fixed ───

class FixedChunker:
    """N Zeichen pro Chunk mit M Zeichen Overlap."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[Chunk]:
        if not text:
            return []
        chunks = []
        i = 0
        n = 0
        while i < len(text):
            end = min(i + self.chunk_size, len(text))
            piece = text[i:end]
            chunks.append(self._make(piece, n))
            n += 1
            if end == len(text):
                break
            i += self.chunk_size - self.overlap
        return chunks

    def _make(self, text: str, idx: int) -> Chunk:
        return Chunk(
            text=text,
            token_count=count_tokens(text),
            char_count=len(text),
            strategy="fixed",
            metadata={"index": idx, "size": self.chunk_size, "overlap": self.overlap},
        )


# ─── Strategy 2: Sliding (größerer Overlap) ───

class SlidingChunker(FixedChunker):
    """Wie Fixed, aber 30% Overlap für mehr Kontext-Erhalt."""

    def __init__(self, chunk_size: int = 1000, overlap_ratio: float = 0.3):
        overlap = int(chunk_size * overlap_ratio)
        super().__init__(chunk_size=chunk_size, overlap=overlap)
        self.strategy_name = "sliding"


# ─── Strategy 3: Semantic (Satzgrenzen) ───

class SemanticChunker:
    """Respektiert Satzgrenzen, gruppiert nach Token-Budget."""

    def __init__(self, max_tokens: int = 500, min_tokens: int = 100):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    def chunk(self, text: str) -> list[Chunk]:
        if not text:
            return []
        # Split in Sätze
        sentences = self._split_sentences(text)
        chunks = []
        current = []
        current_tokens = 0
        idx = 0
        for sent in sentences:
            sent_tokens = count_tokens(sent)
            if current_tokens + sent_tokens > self.max_tokens and current:
                piece = " ".join(current)
                chunks.append(Chunk(
                    text=piece,
                    token_count=count_tokens(piece),
                    char_count=len(piece),
                    strategy="semantic",
                    metadata={"index": idx, "sentences": len(current)},
                ))
                idx += 1
                current = []
                current_tokens = 0
            current.append(sent)
            current_tokens += sent_tokens
        if current:
            piece = " ".join(current)
            chunks.append(Chunk(
                text=piece,
                token_count=count_tokens(piece),
                char_count=len(piece),
                strategy="semantic",
                metadata={"index": idx, "sentences": len(current)},
            ))
        return chunks

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        # Sehr simple Satz-Splitter: ., !, ?, \n\n
        parts = re.split(r"(?<=[.!?])\s+|\n\n+", text)
        return [p.strip() for p in parts if p.strip()]


# ─── Strategy 4: Markdown-aware ───

class MarkdownChunker:
    """Markdown-Struktur als Boundaries. Respektiert Headers, Code-Blöcke, Listen."""

    def __init__(self, max_tokens: int = 800):
        self.max_tokens = max_tokens

    def chunk(self, text: str) -> list[Chunk]:
        if not text:
            return []
        # Split by headers (H1-H6) but keep them
        sections = self._split_by_headers(text)
        chunks = []
        idx = 0
        for header, body in sections:
            piece = header + body if header else body
            if count_tokens(piece) <= self.max_tokens:
                chunks.append(Chunk(
                    text=piece,
                    token_count=count_tokens(piece),
                    char_count=len(piece),
                    strategy="markdown",
                    metadata={"index": idx, "header": header.strip()},
                ))
                idx += 1
            else:
                # Sub-chunk the body
                sub = self._subchunk(body, self.max_tokens)
                for s in sub:
                    chunks.append(Chunk(
                        text=header + s if header else s,
                        token_count=count_tokens(header + s if header else s),
                        char_count=len(header + s if header else s),
                        strategy="markdown",
                        metadata={"index": idx, "header": header.strip(), "subchunked": True},
                    ))
                    idx += 1
        return chunks

    @staticmethod
    def _split_by_headers(text: str) -> list[tuple[str, str]]:
        lines = text.split("\n")
        sections = []
        current_header = ""
        current_body = []
        for line in lines:
            if re.match(r"^#{1,6}\s+", line):
                if current_header or current_body:
                    sections.append((current_header, "\n".join(current_body)))
                current_header = line + "\n"
                current_body = []
            else:
                current_body.append(line)
        if current_header or current_body:
            sections.append((current_header, "\n".join(current_body)))
        return sections

    @staticmethod
    def _subchunk(text: str, max_tokens: int) -> list[str]:
        # Split by paragraphs, accumulate to max_tokens
        paragraphs = text.split("\n\n")
        result = []
        current = []
        current_tokens = 0
        for p in paragraphs:
            pt = count_tokens(p)
            if current_tokens + pt > max_tokens and current:
                result.append("\n\n".join(current))
                current = []
                current_tokens = 0
            current.append(p)
            current_tokens += pt
        if current:
            result.append("\n\n".join(current))
        return result


# ─── Strategy 5: Code-aware ───

class CodeChunker:
    """Source-Code Chunker: Funktionen/Klassen/Top-Level als Units.

    Supported: Python, JavaScript, TypeScript, Go, Rust, Java, C/C++.
    """

    LANG_PATTERNS = {
        "python": [
            re.compile(r"^(async\s+)?def\s+\w+", re.MULTILINE),
            re.compile(r"^class\s+\w+", re.MULTILINE),
        ],
        "javascript": [
            re.compile(r"^(async\s+)?function\s+\w+", re.MULTILINE),
            re.compile(r"^(const|let|var)\s+\w+\s*=\s*(\(|async)", re.MULTILINE),
            re.compile(r"^class\s+\w+", re.MULTILINE),
        ],
        "typescript": [
            re.compile(r"^(async\s+)?function\s+\w+", re.MULTILINE),
            re.compile(r"^(const|let|var)\s+\w+\s*[=:]\s*(\(|async)", re.MULTILINE),
            re.compile(r"^(export\s+)?class\s+\w+", re.MULTILINE),
            re.compile(r"^(export\s+)?interface\s+\w+", re.MULTILINE),
        ],
        "go": [
            re.compile(r"^func\s+(\(\w+\s+\*?\w+\)\s+)?\w+", re.MULTILINE),
            re.compile(r"^type\s+\w+\s+struct", re.MULTILINE),
        ],
        "rust": [
            re.compile(r"^(pub\s+)?(async\s+)?fn\s+\w+", re.MULTILINE),
            re.compile(r"^(pub\s+)?struct\s+\w+", re.MULTILINE),
            re.compile(r"^(pub\s+)?impl\s+\w+", re.MULTILINE),
        ],
    }

    def __init__(self, max_tokens: int = 1000, language: str = "auto"):
        self.max_tokens = max_tokens
        self.language = language

    def chunk(self, text: str, language: str | None = None) -> list[Chunk]:
        lang = language or self.language
        if lang == "auto":
            lang = self._detect_language(text)
        patterns = self.LANG_PATTERNS.get(lang, self.LANG_PATTERNS["python"])

        # Find all function/class boundaries
        boundaries = []
        for pat in patterns:
            for m in pat.finditer(text):
                boundaries.append(m.start())
        boundaries = sorted(set(boundaries))

        if not boundaries:
            # Fallback: fixed chunking
            return FixedChunker(chunk_size=1500, overlap=100).chunk(text)

        # Build chunks from boundaries
        chunks = []
        idx = 0
        for i, start in enumerate(boundaries):
            end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
            piece = text[start:end].rstrip()
            if count_tokens(piece) <= self.max_tokens:
                chunks.append(Chunk(
                    text=piece,
                    token_count=count_tokens(piece),
                    char_count=len(piece),
                    strategy="code",
                    metadata={"index": idx, "language": lang},
                ))
                idx += 1
            else:
                # Sub-chunk: split at next function or by line count
                sub = self._subchunk_function(piece, self.max_tokens)
                for s in sub:
                    chunks.append(Chunk(
                        text=s,
                        token_count=count_tokens(s),
                        char_count=len(s),
                        strategy="code",
                        metadata={"index": idx, "language": lang, "subchunked": True},
                    ))
                    idx += 1
        return chunks

    @staticmethod
    def _detect_language(text: str) -> str:
        if "def " in text and "import " in text and ":" in text:
            return "python"
        if "function " in text or "const " in text or "=>" in text:
            return "javascript"
        if "interface " in text or ": " in text and "type " in text:
            return "typescript"
        if "func " in text and "package " in text:
            return "go"
        if "fn " in text and "let " in text:
            return "rust"
        return "python"

    @staticmethod
    def _subchunk_function(text: str, max_tokens: int) -> list[str]:
        # Split at logical points (blank lines) and accumulate
        blocks = re.split(r"\n\s*\n", text)
        result = []
        current = []
        current_tokens = 0
        for b in blocks:
            bt = count_tokens(b)
            if current_tokens + bt > max_tokens and current:
                result.append("\n\n".join(current))
                current = []
                current_tokens = 0
            current.append(b)
            current_tokens += bt
        if current:
            result.append("\n\n".join(current))
        return result


# ─── Auto-Selector ───

def select_chunker(source_path: str, content: str, **kwargs) -> Chunker:
    """Wähle automatisch die beste Chunking-Strategie basierend auf Inhalt."""
    path = source_path.lower()
    # Code
    if any(path.endswith(ext) for ext in [".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp"]):
        return CodeChunker(**{k: v for k, v in kwargs.items() if k in ["max_tokens", "language"]})
    # Markdown
    if any(path.endswith(ext) for ext in [".md", ".markdown"]):
        return MarkdownChunker(**{k: v for k, v in kwargs.items() if k == "max_tokens"})
    # Default: semantic
    return SemanticChunker(
        **{k: v for k, v in kwargs.items() if k in ["max_tokens", "min_tokens"]}
    )
