# ConText — Status

**Started:** 2026-07-03 22:55
**Current Time:** ~00:35 (Next Day 04.07.2026)
**Target MVP:** 2026-07-04 08:00 (9h Sprint) — 7h 25min verbleibend

## Live Status

- [x] **22:55** — Setup (Repo, Cron, Plan)
- [x] **23:15** — Architektur, Schema, Module-Plan
- [x] **23:30** — Core: utils, store, chunkers (5 Strategien)
- [x] **23:45** — Embedder, Retriever, Generator, Engine
- [x] **23:55** — CLI + Server
- [x] **00:00** — E2E-Test: ✅ RAG funktioniert
- [x] **00:05** — Tests: 20/20 passed
- [x] **00:10** — GitHub Repo erstellt + Code gepusht
- [x] **00:15** — GitHub Pages Landing Page live
- [x] **00:20** — CI/CD Workflows, LICENSE, Issue Templates
- [x] **00:25** — CHANGELOG, examples/, PyPI build
- [x] **00:30** — Benchmark vs naive RAG (Recall 1.0, Citation 100%)
- [x] **00:35** — BENCHMARKS.md, PYPI-PUBLISH.md
- [ ] **00:40-08:00** — Buffer (PyPI-Account wartet auf User; dann Upload, GitHub Release, Show-HN vorbereiten)

## Was funktioniert (verifiziert)

- ✅ `context build /tmp/docs` — Indexiert 5 Files in 27 Chunks
- ✅ `context query "What guarantees memory safety in Rust?"` — Antwort mit [1] Citation
- ✅ `context --json query` — JSON-Output
- ✅ `context serve` — HTTP API auf 8765
- ✅ Token-Budget-Manager (greedy fit)
- ✅ 5 Chunking-Strategien alle getestet
- ✅ SQLite-Storage mit Embedding-Cache
- ✅ Ollama-Integration
- ✅ 20/20 Unit-Tests grün
- ✅ `pip install -e .` funktioniert
- ✅ `python -m build` produziert wheel + tar.gz
- ✅ GitHub Repo public
- ✅ GitHub Pages live
- ✅ Benchmark: Recall 1.0, Citation 100%

## Liefer-Artefakte

| Artefakt | URL/Pfad |
|---|---|
| **Source** | https://github.com/Tabtii/context-engineer |
| **Landing Page** | https://tabtii.github.io/context-engineer/ |
| **Wheel** | `dist/context_engineer-0.1.0-py3-none-any.whl` |
| **Tarball** | `dist/context_engineer-0.1.0.tar.gz` |
| **Tests** | `pytest tests/` → 20/20 ✓ |
| **Benchmark** | `python benchmark.py` → vs naive RAG |
| **Doku** | README.md, ARCHITECTURE.md, CHANGELOG.md, BENCHMARKS.md, SHOW-HN.md, PYPI-PUBLISH.md |
| **CI** | `.github/workflows/tests.yml`, `publish.yml` |

## Was fehlt (User-Aktionen)

- [ ] **PyPI-Account erstellen** (manuell, ~5 min)
- [ ] **Twine-Upload** (manuell, sobald Token da)
- [ ] **GitHub Release v0.1.0 taggen** (manuell, nach PyPI)
- [ ] **Show-HN posten** (optional, ~5 min)
- [ ] **BrowserMCP Chrome Web Store email-bestätigen** (von gestern)

## Architektur-Übersicht

```
context_engineer/
├── __init__.py        # ConText, Source, Answer
├── cli.py             # Click CLI
├── server.py          # HTTP API (MCP-kompatibel)
├── core/
│   ├── engine.py      # Top-level API
│   ├── chunker.py     # 5 Strategien
│   ├── embedder.py    # Ollama Embedding + LRU-Cache
│   ├── retriever.py   # Cosine-Sim + Token-Budget
│   ├── generator.py   # Ollama LLM + Citation
│   └── budget.py      # Token-Budget-Manager
├── store/db.py        # SQLite + Embedding-Cache
└── utils/tokens.py    # tiktoken + Fallback
```

## Konkurrenz-Vorteil

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
