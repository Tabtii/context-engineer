# ConText

> **Context-Engineer for local AI Agents.** Zero-config RAG for Ollama with automatic chunking, token-budget awareness, and source citation.

```bash
pip install context-engineer
ollama pull nomic-embed-text
ollama pull llama3.2

context build ./docs
context query "What is the main topic?"
```

## Why ConText?

Most RAG pipelines force you to choose between **LangChain's** complexity, **ChromaDB's** infrastructure, and **naive vector search's** poor results. ConText is the third option: **opinionated, local-first, zero-config**.

| Feature | ConText | LangChain | LlamaIndex | Naive RAG |
|---|---|---|---|---|
| **Setup time** | 30 seconds | 30 minutes | 20 minutes | 5 minutes |
| **Auto chunking** | ✅ 5 strategies | ⚠️ DIY | ✅ | ❌ Fixed only |
| **Token-budget aware** | ✅ | ⚠️ DIY | ⚠️ DIY | ❌ |
| **Source citation** | ✅ Built-in | ⚠️ DIY | ⚠️ DIY | ❌ |
| **Runs offline** | ✅ Ollama only | ✅ | ✅ | ❌ |
| **Dependencies** | 5 packages | 30+ | 20+ | varies |
| **Storage** | SQLite | optional | optional | in-memory |

## Features

- 🎯 **5 Chunking Strategies** — Auto-selected per file type (markdown, code, semantic, fixed, sliding)
- 💰 **Token-Budget Manager** — Fits retrieved chunks to your model's context window
- 📚 **Source Citation** — Every answer includes `[1]`, `[2]`, `[3]` references
- 🚀 **Zero Dependencies** — Just `pip install context-engineer` + Ollama running locally
- 💾 **SQLite Storage** — No external vector database needed
- 🔌 **HTTP API** — MCP-compatible server for IDE integration
- 📊 **Built-in Benchmarks** — Compare against naive RAG baseline

## Quick Start

### 1. Install

```bash
pip install context-engineer
```

### 2. Install Ollama models

```bash
# Embedding model (required)
ollama pull nomic-embed-text

# LLM model (pick one)
ollama pull llama3.2          # 2GB, fast
ollama pull qwen2.5-coder    # 4GB, code-specialized
ollama pull mistral          # 4GB, general
```

### 3. Index your docs

**Option A: Local files**

```bash
context build ./docs
```

This recursively finds all `.md`, `.txt`, `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.json`, `.yaml`, `.yml` files and indexes them with the right chunker.

**Option B: Crawl a website**

```bash
context crawl https://docs.example.com --max-pages 20
```

Respects `robots.txt`, BFS-crawls same-domain pages, removes script/style/nav/footer.

### 4. Ask questions

```bash
context query "What guarantees memory safety in Rust?"
```

Output:

```
╭─ Answer (27295ms, 714+97 tokens) ─────────────────╮
│ Rust's ownership system guarantees memory safety   │
│ at compile time. Every value has an owner, and     │
│ there can only be one owner at a time. When the    │
│ owner goes out of scope, the value is dropped [1]. │
╰────────────────────────────────────────────────────╯
Sources
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┓
┃ # ┃ Source               ┃ Strategy ┃ Score ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━┩
│ 1 │ rust-intro.md        │ markdown │ 0.855 │
│ 2 │ rust-intro.md        │ markdown │ 0.765 │
└───┴──────────────────────┴──────────┴───────┘
```

## Python API

```python
from context_engineer import ConText

# Initialize
ctx = ConText(
    db_path=".context/store.db",
    llm_model="llama3.2",
    embed_model="nomic-embed-text",
    context_window=8192,
)

# Index files
ctx.build("./docs")

# Add raw text
ctx.add_text("Some important info", source="notes.md")

# Query
answer = ctx.query("What is X?")
print(answer.text)        # "X is ... [1]"
print(answer.sources)     # [Source(...), ...]
print(answer.latency_ms)  # 1234

# Stats
ctx.stats()
# {'documents': 5, 'chunks': 27, 'embeddings': 27, ...}
```

## HTTP API

```bash
context serve --port 8765
```

```bash
# Query
curl -X POST http://localhost:8765/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is X?"}'

# Build
curl -X POST http://localhost:8765/build \
  -H "Content-Type: application/json" \
  -d '{"path": "./docs"}'

# Stats
curl http://localhost:8765/stats
```

## Architecture

```
ConText Pipeline
    │
    ├─ Document Loader (.md, .py, .js, ...)
    │       │
    │       ▼
    ├─ Auto-Selected Chunker
    │       │
    │       ├─ Markdown   (headers, code blocks)
    │       ├─ Code       (functions, classes)
    │       ├─ Semantic   (sentence boundaries)
    │       ├─ Fixed      (N chars, M overlap)
    │       └─ Sliding    (larger overlap)
    │       │
    │       ▼
    ├─ Embedder (Ollama nomic-embed-text + LRU cache)
    │       │
    │       ▼
    ├─ SQLite Store (chunks + vectors as BLOB)
    │
    └─ Query
        │
        ├─ Cosine-Similarity (top-20)
        │
        ├─ Token-Budget Greedy-Fit
        │
        └─ LLM Generation (Ollama llama3.2)
            │
            └─ Cited Response [1][2][3]
```

## CLI Reference

```
context build <path>          Index documents
context query "question"      Ask a question (with sources)
context stats                  Show database stats
context list                   List indexed documents
context remove <source>        Remove a document
context serve                  Start HTTP API server
```

Global options:
- `--db PATH` — SQLite database location (default: `.context/store.db`)
- `--llm MODEL` — Ollama LLM model (default: `llama3.2`)
- `--embed MODEL` — Ollama embed model (default: `nomic-embed-text`)
- `--ollama-url URL` — Ollama API (default: `http://localhost:11434`)
- `--context-window N` — LLM context window (default: 8192)

## Roadmap

- [x] v0.1.0 — Core RAG + 5 chunkers + CLI + HTTP API
- [ ] v0.2.0 — Hybrid search (BM25 + vector)
- [ ] v0.3.0 — Cross-encoder reranking
- [ ] v0.4.0 — Multi-modal (image + text)
- [ ] v0.5.0 — Cloud sync + team features (Pro)
- [ ] v1.0.0 — Stable API

## License

MIT © 2026 Torben

## See Also

- [Ollama](https://ollama.com) — Local LLM runtime
- [Architecture docs](./ARCHITECTURE.md)
- [Status & Roadmap](./STATUS.md)
- [Benchmark results](./BENCHMARKS.md)
