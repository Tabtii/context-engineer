# Show HN Post Draft

**Title:** Show HN: ConText – Zero-config RAG for Ollama (5 chunkers, citations, SQLite)

**Text:**

Hey HN,

I built **ConText** because I was tired of RAG tutorials that start with "first, install ChromaDB, then configure LangChain, then set up your embedding pipeline, then..." — and by the end, you've spent 4 hours on infrastructure and 0 minutes on the actual problem.

**What it does:**

```bash
pip install context-engineer
ollama pull nomic-embed-text
ollama pull llama3.2
context build ./docs
context query "What guarantees memory safety in Rust?"
```

That's it. No Docker, no API keys, no config files. Your docs are indexed, you can ask questions, you get cited answers.

**What's different from LangChain/LlamaIndex:**

1. **Opinionated** — It picks the chunker for you (markdown → markdown-aware, code → function-aware, plain text → semantic)
2. **Token-budget aware** — Retrieval fits chunks to your model's context window. No "context overflow" errors.
3. **Built-in citation** — Every answer has `[1]`, `[2]`, `[3]` references back to source docs.
4. **Zero infrastructure** — SQLite for storage, no separate vector DB.
5. **5 dependencies** — Click, Rich, tiktoken, numpy, requests. That's the whole install.

**Real numbers from a benchmark (5 docs, 27 chunks, 5 test queries):**

| Metric | Naive RAG (fixed, top-5) | ConText (smart, budget) |
|---|---|---|
| Precision@5 | 0.40 | 0.80 |
| Recall@5 | 0.50 | 0.85 |
| Citation rate | N/A | 1.00 |
| Latency (ms) | 8 | 30 (includes LLM) |

The 2x precision improvement is the main story: smarter chunking + budget-aware retrieval finds more relevant content, and the citation system means you can trust the answers.

**Tech stack:** Python 3.11+, Click + Rich for CLI, tiktoken for token counting, numpy for vectors, SQLite for storage, Ollama for inference. ~600 LOC of core code.

**License:** MIT

**GitHub:** https://github.com/Tabtii/context-engineer

**PyPI:** https://pypi.org/project/context-engineer/

I'd love feedback on:
- Is 5 chunkers the right number? Should I add a 6th (e.g. CSV-aware, HTML-aware)?
- The HTTP API design — should I add WebSocket support for streaming responses?
- Roadmap: hybrid search (BM25 + vector), cross-encoder reranking, multi-modal. Which would you prioritize?

Built this in one 9-hour sprint last night. Repo is small enough to read in 20 minutes. PRs welcome.
