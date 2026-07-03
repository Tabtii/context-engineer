# Changelog

All notable changes to ConText are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-04

### Added

- **5 chunking strategies:** `fixed`, `sliding`, `semantic`, `markdown`, `code`
- **Auto chunker selection** based on file extension
- **Token-budget-aware retrieval** with greedy fit algorithm
- **Ollama integration** for embeddings (`nomic-embed-text`) and LLM inference
- **SQLite storage** with BLOB-based embedding cache
- **Source citation** in `[1]`, `[2]`, `[3]` format
- **Click CLI** with `build`, `query`, `stats`, `list`, `remove`, `serve` commands
- **HTTP API server** (MCP-compatible) at `127.0.0.1:8765`
- **In-memory embedding cache** with LRU eviction (10k entries)
- **Benchmark suite** comparing ConText vs naive RAG
- **GitHub Pages landing page** at https://tabtii.github.io/context-engineer/
- **20 unit tests** with 100% pass rate
- **GitHub Actions CI** for tests + PyPI publish

### Performance

- Indexing 5 docs (16 KB) into 27 chunks: ~2s
- Query latency: 8-30s including LLM generation
- Cache hit rate for repeated queries: 100%

[0.1.0]: https://github.com/Tabtii/context-engineer/releases/tag/v0.1.0
