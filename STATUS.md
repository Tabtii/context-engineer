# ConText — Status

**Started:** 2026-07-03 22:55
**Current Time:** ~23:25 (Updated)
**Target MVP:** 2026-07-04 08:00 (9h Sprint)

## Live Status

- [x] **22:55** — Setup (Repo, Cron, Plan)
- [x] **23:15** — Architektur, Schema, Module-Plan
- [x] **23:30** — Core: utils, store, chunkers (5 Strategien)
- [x] **23:45** — Embedder, Retriever, Generator, Engine
- [x] **23:55** — CLI + Server
- [x] **00:00** — E2E-Test: ✅ RAG funktioniert (Score 0.855 für Rust Memory-Safety)
- [x] **00:05** — Tests: 20/20 passed
- [x] **00:10** — GitHub Repo erstellt + Code gepusht
- [x] **00:15** — GitHub Pages Landing Page live: https://tabtii.github.io/context-engineer/
- [x] **00:20** — CI/CD Workflows, LICENSE, Issue Templates
- [x] **00:25** — CHANGELOG, examples/, PyPI build (wheel + tar.gz)
- [ ] **~00:30** — Benchmark vs naive RAG (running, ~3 min)
- [ ] **00:35** — Final polish, push alles
- [ ] **00:40-07:00** — Buffer (Bench-Schreiben, Blog-Post, evt. Twitter)
- [ ] **07:00-08:00** — Final-Check
- [ ] **08:00** — Wake-Up-Report via Cron

## Was funktioniert (verifiziert)

- ✅ `context build /tmp/docs` — Indexiert 5 Files in 27 Chunks (Markdown + Code Strategie)
- ✅ `context query "What guarantees memory safety in Rust?"` — Antwort mit [1] Citation
- ✅ `context --json query` — JSON-Output für Programmatic-Access
- ✅ `context serve` — HTTP API auf 8765
- ✅ Token-Budget-Manager (greedy fit, korrekt)
- ✅ 5 Chunking-Strategien alle getestet
- ✅ SQLite-Storage mit Embedding-Cache
- ✅ Ollama-Integration (embedding + chat)
- ✅ 20/20 Unit-Tests grün
- ✅ `pip install -e .` funktioniert
- ✅ `python -m build` produziert wheel + tar.gz
- ✅ GitHub Repo public: https://github.com/Tabtii/context-engineer
- ✅ GitHub Pages live: https://tabtii.github.io/context-engineer/

## Liefer-Artefakte

| Artefakt | Pfad/URL |
|---|---|
| **Source** | https://github.com/Tabtii/context-engineer |
| **Landing Page** | https://tabtii.github.io/context-engineer/ |
| **Wheel** | `dist/context_engineer-0.1.0-py3-none-any.whl` |
| **Tarball** | `dist/context_engineer-0.1.0.tar.gz` |
| **Tests** | `pytest tests/` → 20/20 ✓ |
| **Benchmark** | `python benchmark.py` → vs naive RAG |
| **Doku** | README.md, ARCHITECTURE.md, CHANGELOG.md, SHOW-HN.md |
| **CI** | `.github/workflows/tests.yml`, `publish.yml` |

## Architektur

```
context_engineer/
├── __init__.py        # ConText, Source, Answer
├── cli.py             # Click CLI (build, query, stats, list, remove, serve)
├── server.py          # HTTP API (MCP-kompatibel)
├── core/
│   ├── engine.py      # Top-level API
│   ├── chunker.py     # 5 Strategien: fixed/sliding/semantic/markdown/code
│   ├── embedder.py    # Ollama Embedding + LRU-Cache
│   ├── retriever.py   # Cosine-Sim + Token-Budget
│   ├── generator.py   # Ollama LLM + Citation
│   └── budget.py      # Token-Budget-Manager
├── store/db.py        # SQLite + Embedding-Cache
└── utils/tokens.py    # tiktoken + Fallback
```

## Konkurrenz-Vorteil (für Show-HN)

| | ConText | LangChain | LlamaIndex | Naive |
|---|---|---|---|---|
| Setup | **30s** | 30min | 20min | 5min |
| Auto-Chunking | **5 Strategien** | DIY | 3-4 | Fixed |
| Token-Budget | **Built-in** | DIY | DIY | — |
| Citation | **Built-in** | DIY | DIY | — |
| Deps | **5** | 30+ | 20+ | varies |
| Storage | **SQLite** | optional | optional | RAM |

## Tech-Stack

- **Sprache:** Python 3.11+
- **CLI:** Click + Rich
- **LLM:** Ollama (llama3.2, ornith-9b, gemma-4 — alle lokal)
- **Embeddings:** nomic-embed-text via Ollama
- **Storage:** SQLite (kein externer Vector-DB)
- **Distribution:** PyPI + GitHub
