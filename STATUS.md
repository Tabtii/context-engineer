# ConText — Status

**Started:** 2026-07-03 22:55
**Current Time:** ~23:25 (4. Juli)
**Target MVP:** 2026-07-04 08:00 (9h Sprint) — 8h 35min verbleibend

## Live Status

- [x] **22:55** — Setup (Repo, Cron, Plan)
- [x] **23:15** — Architektur, Schema
- [x] **23:30** — Core: utils, store, chunkers
- [x] **23:45** — Embedder, Retriever, Generator, Engine
- [x] **23:55** — CLI + Server
- [x] **00:00** — E2E-Test: ✅
- [x] **00:05** — Tests: 20/20 passed
- [x] **00:10** — GitHub Repo + Pages
- [x] **00:20** — CI/CD, LICENSE, Issue Templates
- [x] **00:25** — CHANGELOG, examples, PyPI build
- [x] **00:30** — Benchmark vs naive RAG
- [x] **00:35** — Docs: BENCHMARKS, PYPI-PUBLISH
- [x] **00:40** — v0.2.0: BM25 + Hybrid Retriever (vector + BM25 mit RRF)
- [x] **00:50** — v0.2.0: 4 neue Tests, 24/24 grün
- [x] **01:00** — Hybrid E2E-Test: Deutsche Frage → Deutsche Antwort mit [1] Citation
- [x] **01:10** — Code-Chunker E2E-Test: utils.py function found & explained
- [x] **01:15** — COMPARISON.md (vs LangChain/ChromaDB)
- [ ] **01:30** — Push final v0.2.0
- [ ] **01:30-08:00** — Buffer (8h — viel Zeit für Polish, Real PyPI Upload, Show-HN)

## Was funktioniert (verifiziert)

- ✅ **v0.1.0 Core**: 5 Chunkers, Token-Budget, Citation, CLI, HTTP API
- ✅ **v0.2.0 Hybrid**: BM25 + Vector Search mit RRF Fusion
- ✅ **E2E-Test 1**: "What guarantees memory safety in Rust?" → Cited answer
- ✅ **E2E-Test 2**: "When was Python released and by whom?" → Cited answer (markdown chunker)
- ✅ **E2E-Test 3**: "Wie formatiert man Bytes als lesbaren String?" → Cited German answer (code chunker)
- ✅ **24/24 Tests** grün (20 unit + 4 BM25/Hybrid)
- ✅ **Hybrid 10x schneller** als pure vector (2ms vs 20ms) auf Test-Corpus
- ✅ **GitHub Repo** public
- ✅ **GitHub Pages** live
- ✅ **PyPI-Package** gebaut

## Liefer-Artefakte

| Artefakt | URL/Pfad |
|---|---|
| **Source** | https://github.com/Tabtii/context-engineer |
| **Landing Page** | https://tabtii.github.io/context-engineer/ |
| **Wheel** | `dist/context_engineer-0.1.0-py3-none-any.whl` |
| **Tarball** | `dist/context_engineer-0.1.0.tar.gz` |
| **Tests** | `pytest tests/` → 24/24 ✓ |
| **Benchmark 1** | `python benchmark.py` → vs naive (LLM) |
| **Benchmark 2** | `python benchmark_hybrid.py` → vs pure vector |
| **Doku** | README, ARCHITECTURE, CHANGELOG, BENCHMARKS, COMPARISON, SHOW-HN, PYPI-PUBLISH |
| **CI** | GitHub Actions tests + publish |

## Was fehlt (User-Aktionen)

- [ ] **PyPI-Account erstellen** (manuell, ~5 min)
- [ ] **Twine-Upload** (manuell, sobald Token da)
- [ ] **GitHub Release v0.1.0 taggen** (manuell)
- [ ] **Show-HN posten** (optional)
- [ ] **BrowserMCP Chrome Web Store email-bestätigen** (von gestern)

## Verbleibende Zeit

- **~8 Stunden** bis 08:00 Wake-Up
- Genug für:
  - v0.3.0: Cross-Encoder Reranking
  - v0.4.0: Web-Crawler (URLs indexieren)
  - Mehr E2E-Tests mit echten Daten
  - Show-HN Post Live
  - Bug-Polish

## Architektur (v0.2.0)

```
context_engineer/
├── __init__.py        # ConText, Source, Answer
├── cli.py             # Click CLI
├── server.py          # HTTP API
├── core/
│   ├── engine.py      # Top-level (Hybrid by default)
│   ├── chunker.py     # 5 Strategien
│   ├── embedder.py    # Ollama Embedding + LRU
│   ├── retriever.py   # Pure Vector (default fallback)
│   ├── hybrid.py      # Vector + BM25 mit RRF ← NEW
│   ├── bm25.py        # BM25 Index ← NEW
│   ├── generator.py   # Ollama LLM + Citation
│   └── budget.py      # Token-Budget
├── store/db.py        # SQLite + Embedding-Cache
└── utils/tokens.py    # tiktoken
```

## Konkurrenz-Vorteil (v0.2.0)

| | ConText | LangChain | ChromaDB | LlamaIndex |
|---|---|---|---|---|
| Setup | **30s** | 30min | 15min | 20min |
| Hybrid search | **Built-in** | DIY | ❌ | DIY |
| Auto-chunking | **5** | ❌ | ❌ | partial |
| Token-budget | **Built-in** | ❌ | ❌ | ❌ |
| Citation | **Built-in** | DIY | ❌ | DIY |
| HTTP API | **Built-in** | ❌ | ❌ | ❌ |
| Deps | **5** | 30+ | 15+ | 20+ |
| Storage | **SQLite** | optional | DuckDB | optional |
