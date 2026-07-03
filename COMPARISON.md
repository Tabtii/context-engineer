# ConText vs LangChain vs ChromaDB — Real-world comparison

## Setup (5 min for ConText, 60 min for LangChain)

### ConText

```bash
pip install context-engineer
ollama pull nomic-embed-text llama3.2
context build ./docs
```

That's it. 30 seconds.

### LangChain + ChromaDB

```bash
pip install langchain chromadb sentence-transformers
```

Then you need:
1. Pick a document loader (5+ options, none perfect for mixed files)
2. Pick a text splitter (10+ options, each with 5+ parameters)
3. Pick an embedding model (HuggingFace, OpenAI, Cohere, ...)
4. Pick a vector store (ChromaDB, FAISS, Pinecone, Weaviate, ...)
5. Pick a retriever (vector, BM25, hybrid, multi-query, self-query, ...)
6. Pick an LLM (OpenAI, Anthropic, Ollama, vLLM, ...)
7. Write ~200 lines of glue code
8. Debug

Time: 30-60 minutes for an experienced dev. 1-2 days if you're new.

## Code Comparison

### ConText (3 lines)

```python
from context_engineer import ConText
ctx = ConText()
ctx.build("./docs")
answer = ctx.query("What guarantees memory safety in Rust?")
print(answer.text)  # "...[1]"
print(answer.sources)  # [Source(...)]
```

### LangChain + ChromaDB (~30 lines)

```python
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import Ollama
from langchain.chains import RetrievalQA

# 1. Load
loader = DirectoryLoader('./docs', glob='**/*.md')
docs = loader.load()

# 2. Split
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = splitter.split_documents(docs)

# 3. Embed
embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')

# 4. Store
db = Chroma.from_documents(splits, embeddings, persist_directory='./chroma')

# 5. LLM
llm = Ollama(model='llama3.2')

# 6. Chain
qa = RetrievalQA.from_chain_type(
    llm=llm, chain_type='stuff', retriever=db.as_retriever()
)

# 7. Query
result = qa.run("What guarantees memory safety in Rust?")
# No citations! No source metadata in output!
```

## Feature Comparison

| Feature | ConText | LangChain | ChromaDB | LlamaIndex |
|---|---|---|---|---|
| **Setup time** | 30s | 30min | 15min | 20min |
| **Lines for hello-world RAG** | 3 | ~30 | ~20 | ~15 |
| **Auto chunker selection** | ✅ | ❌ | ❌ | ⚠️ partial |
| **Source citation** | ✅ built-in | ⚠️ DIY | ❌ | ⚠️ DIY |
| **Token-budget aware** | ✅ built-in | ❌ | ❌ | ❌ |
| **Hybrid search (BM25+vec)** | ✅ | ⚠️ DIY | ❌ | ⚠️ DIY |
| **Storage** | SQLite | optional | DuckDB/ClickHouse | optional |
| **HTTP API** | ✅ built-in | ❌ | ❌ | ❌ |
| **MCP-compatible server** | ✅ | ❌ | ❌ | ❌ |
| **Total dependencies** | 5 | 30+ | 15+ | 20+ |
| **Works offline** | ✅ | ✅ | ✅ | ✅ |

## What You Get With ConText That Others Don't

### 1. Token-Budget-Aware Retrieval

ConText's `BudgetConfig` automatically fits retrieved chunks to your model's context window:

```python
ctx = ConText(context_window=4096)  # fits a 4k model
# Retrieval will never exceed ~2.7k tokens for chunks
# (reserving 1k for response, 256 for system, 100 for citations)
```

LangChain: you manually truncate or use `max_tokens_limit` (which is approximate).

### 2. Built-in Source Citation

Every ConText answer has `[1]`, `[2]`, `[3]` references:

```
Rust's ownership system guarantees memory safety [1].
Mozilla adopted Rust for Firefox components [2].
```

LangChain: you have to build a custom prompt with explicit `[doc N]` placeholders and parse the output.

### 3. Auto-Chunker Selection

```python
ctx.build("./docs")  # ConText picks chunker per file:
                      #   .md → MarkdownChunker
                      #   .py → CodeChunker
                      #   .txt → SemanticChunker
```

LangChain: you pick one splitter for the whole corpus, or write a router.

### 4. MCP-Compatible HTTP Server

```bash
context serve --port 8765
```

Then any MCP-aware client (Cursor, Claude Desktop, custom agent) can hit:
- `POST /query` with `{"question": "..."}`
- `POST /build` with `{"path": "..."}`
- `GET /stats`

LangChain: you write your own FastAPI server.

## When to Use What

**Use ConText when:**
- You want RAG working in 5 minutes
- You need citations for compliance/audit
- You're building a local AI agent with Ollama
- You don't want to manage vector DB infrastructure

**Use LangChain when:**
- You need exotic chains (agents, multi-step, tools)
- You're already deep in the LangChain ecosystem
- You need a very specific integration (Slack bot, Notion, etc.)

**Use ChromaDB directly when:**
- You're building a custom pipeline
- You need fine-grained control over the vector store
- You have a specific deployment target (e.g. cloud-managed Chroma)

**Use LlamaIndex when:**
- You're building complex indexing pipelines (multi-modal, hierarchical)
- You need advanced query engines (sub-questions, multi-step)
- You're processing PDFs with tables/images

## The Honest Truth

ConText is **less flexible** than LangChain. LangChain has 200+ integrations; ConText has 1 (Ollama).

ConText is **less powerful** than LlamaIndex for complex indexing.

But ConText is **easier, faster, and 90% of users only need that 10% of features.**

If you want the 90% in 30 seconds: **ConText**.
If you need the other 90% (exotic chains, multi-modal, agents): **LangChain**.

You can always graduate later. Start simple.
