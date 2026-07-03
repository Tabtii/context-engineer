# ConText — Architektur

## Module

```
context_engineer/
├── __init__.py
├── cli.py              # Click CLI: build, query, stats
├── core/
│   ├── __init__.py
│   ├── chunker.py      # 5 Chunking-Strategien
│   ├── embedder.py     # Ollama Embedding-Client
│   ├── retriever.py    # Vektor-Suche + Reranking
│   ├── generator.py    # Ollama LLM Response
│   └── budget.py       # Token-Budget-Manager
├── store/
│   ├── __init__.py
│   ├── db.py           # SQLite Schema + ORM-light
│   └── cache.py        # Embedding-Cache (Hash → Vector)
├── formats/
│   ├── __init__.py
│   ├── markdown.py     # MD-Aware Chunking
│   ├── code.py         # Code-Aware (Python/JS/etc)
│   └── plain.py        # Plain-Text
└── utils/
    ├── __init__.py
    └── tokens.py       # Token-Counter (tiktoken + Ollama-fallback)
```

## Datenbank-Schema (SQLite)

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_type TEXT,           -- 'file', 'url', 'paste'
    content_hash TEXT UNIQUE,   -- SHA-256 für Dedup
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER,
    text TEXT NOT NULL,
    token_count INTEGER,
    char_count INTEGER,
    strategy TEXT,              -- 'fixed', 'semantic', 'sliding', 'markdown', 'code'
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id),
    vector BLOB NOT NULL,       -- numpy.float32[] serialisiert
    model TEXT NOT NULL,        -- 'nomic-embed-text', etc
    dim INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE queries (
    id INTEGER PRIMARY KEY,
    query_text TEXT,
    response_text TEXT,
    retrieved_chunk_ids JSON,   -- [1, 5, 12]
    token_usage JSON,           -- {prompt: 1200, completion: 200}
    latency_ms INTEGER,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Chunking-Strategien

1. **fixed** — N Zeichen pro Chunk mit M Zeichen Overlap
2. **semantic** — Satzgrenzen respektieren, ähnliche Sätze gruppieren
3. **sliding** — Fixed-Größe mit größerem Overlap (30%)
4. **markdown** — Header/Listen/Code-Blöcke als Boundaries
5. **code** — Funktionen/Klassen/Top-Level-Defs als Units

## CLI-Befehle

```bash
context build <path>          # Index Dokumente
context query "frage"          # RAG-Query
context stats                  # DB-Statistiken
context list                   # Alle indexierten Docs
context remove <source>        # Doc entfernen
context serve                  # HTTP-API (für MCP-Integration)
```

## Embedding-Cache

SHA-256(text + model_name) → embedding. Verhindert doppelte Embeddings beim Re-Index.

## Token-Budget-Manager

```
total_context = 8192  (vom Modell)
reserve_for_response = 1024
reserve_for_system_prompt = 256
available_for_chunks = 8192 - 1024 - 256 = 6912

# Sortiere Chunks nach Similarity
# Greedy fit bis Budget voll ist
```

## Design-Entscheidungen

- **SQLite only** (kein ChromaDB/Faiss Dependency) — minimal Install
- **numpy nur als transitive** — kommt mit Ollama/sentence-transformers eh
- **Kein asyncio** — sync API, einfacher zu debuggen
- **tiktoken für Token-Counting** (cl100k_base als Fallback für nicht-OpenAI-Modelle)
- **JSON statt Pickle** für metadata/cache (debuggbar)
