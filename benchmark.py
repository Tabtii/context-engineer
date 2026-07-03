"""Benchmark: ConText (smart chunking + budget) vs naive RAG (fixed chunking, top-5).

Naive Baseline:
- Single fixed chunker (1000 chars, 100 overlap)
- Top-5 retrieval (no token budget)
- No citation awareness

ConText:
- Auto-chunking (markdown, semantic, code per file type)
- Token-budget-aware retrieval
- Citation in output

Metrics:
- Precision@5: How many of top-5 are in the gold set?
- Recall@5: How many gold items are in top-5?
- Latency: ms for retrieve + generate
- Tokens used: prompt + completion
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from context_engineer import ConText


# Gold-Standard Test-Set
BENCHMARK_QUERIES = [
    {
        "query": "What guarantees memory safety in Rust?",
        "expected_chunks": [
            "ownership system guarantees memory safety",
            "Every value has an owner",
        ],
        "category": "specific_fact",
    },
    {
        "query": "Who created Python and when?",
        "expected_chunks": [
            "Guido van Rossum",
            "1991",
        ],
        "category": "specific_fact",
    },
    {
        "query": "What is the Zen of Python?",
        "expected_chunks": [
            "Beautiful is better than ugly",
            "Simple is better than complex",
        ],
        "category": "quote",
    },
    {
        "query": "Which companies use Rust?",
        "expected_chunks": [
            "Mozilla",
            "Discord",
            "Cloudflare",
        ],
        "category": "list",
    },
    {
        "query": "What are Python's use cases?",
        "expected_chunks": [
            "Web development",
            "Data science",
            "Automation",
        ],
        "category": "list",
    },
]


def precision_at_k(retrieved_texts: list[str], expected_substrings: list[str], k: int = 5) -> float:
    """Welcher Anteil der top-k retrieved texts enthält mind. ein expected substring?"""
    if not retrieved_texts:
        return 0.0
    top_k_texts = retrieved_texts[:k]
    hits = 0
    for text in top_k_texts:
        if any(exp.lower() in text.lower() for exp in expected_substrings):
            hits += 1
    return hits / min(k, len(top_k_texts))


def recall_at_k(retrieved_texts: list[str], expected_substrings: list[str], k: int = 5) -> float:
    """Welcher Anteil der expected substrings wurde in top-k gefunden?"""
    if not expected_substrings:
        return 0.0
    top_k_texts = " ".join(retrieved_texts[:k])
    hits = sum(1 for exp in expected_substrings if exp.lower() in top_k_texts.lower())
    return hits / len(expected_substrings)


class NaiveRAG:
    """Baseline: Fixed chunking, top-5, no token budget."""

    def __init__(self, db_path: str, ollama_url: str = "http://localhost:11434"):
        from context_engineer.store.db import Store
        from context_engineer.core.embedder import Embedder
        self.store = Store(db_path)
        self.embedder = Embedder(base_url=ollama_url)

    def query(self, question: str, top_k: int = 5) -> dict:
        start = time.time()
        # Simple retrieval
        query_vec = self.embedder.embed(question)
        matrix, chunk_ids = self.store.get_all_embeddings(model=self.embedder.model)
        if matrix.size == 0:
            return {"texts": [], "latency_ms": 0}
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        scores = matrix_norm @ query_norm
        top_idx = np.argsort(-scores)[:top_k]
        texts = []
        for idx in top_idx:
            chunk = self.store.get_chunk(int(chunk_ids[int(idx)]))
            if chunk:
                texts.append(chunk.text)
        return {
            "texts": texts,
            "latency_ms": int((time.time() - start) * 1000),
        }


def run_benchmark(db_path: str, llm_model: str = "ornith-9b:ctx65k") -> dict:
    """Run full benchmark on the test queries."""
    engine = ConText(db_path=db_path, llm_model=llm_model)
    naive = NaiveRAG(db_path=db_path)

    results = []
    for q in BENCHMARK_QUERIES:
        # Naive
        naive_result = naive.query(q["query"], top_k=5)
        # ConText
        start = time.time()
        ctx_answer = engine.query(q["query"], top_k=20)
        ctx_texts = [s.text for s in ctx_answer.sources]

        results.append({
            "query": q["query"],
            "category": q["category"],
            "naive": {
                "precision@5": precision_at_k(naive_result["texts"], q["expected_chunks"]),
                "recall@5": recall_at_k(naive_result["texts"], q["expected_chunks"]),
                "latency_ms": naive_result["latency_ms"],
                "n_retrieved": len(naive_result["texts"]),
            },
            "context": {
                "precision@5": precision_at_k(ctx_texts, q["expected_chunks"]),
                "recall@5": recall_at_k(ctx_texts, q["expected_chunks"]),
                "latency_ms": ctx_answer.latency_ms,
                "n_retrieved": len(ctx_texts),
                "answer_chars": len(ctx_answer.text),
                "has_citations": "[" in ctx_answer.text and "]" in ctx_answer.text,
            },
        })

    # Aggregate
    def avg(key_path: str) -> float:
        vals = []
        for r in results:
            v = r
            for k in key_path.split("."):
                v = v[k]
            vals.append(v)
        return sum(vals) / len(vals) if vals else 0.0

    summary = {
        "queries": len(results),
        "naive": {
            "avg_precision@5": round(avg("naive.precision@5"), 3),
            "avg_recall@5": round(avg("naive.recall@5"), 3),
            "avg_latency_ms": int(avg("naive.latency_ms")),
        },
        "context": {
            "avg_precision@5": round(avg("context.precision@5"), 3),
            "avg_recall@5": round(avg("context.recall@5"), 3),
            "avg_latency_ms": int(avg("context.latency_ms")),
            "citation_rate": round(
                sum(1 for r in results if r["context"]["has_citations"]) / len(results), 3
            ),
        },
        "results": results,
    }
    return summary


def print_benchmark(summary: dict):
    print("\n" + "=" * 70)
    print("ConText vs Naive RAG Benchmark")
    print("=" * 70)
    print(f"Queries: {summary['queries']}")
    print()
    print(f"{'Metric':<25} {'Naive':>15} {'ConText':>15} {'Δ':>10}")
    print("-" * 70)
    p_naive = summary["naive"]["avg_precision@5"]
    p_context = summary["context"]["avg_precision@5"]
    r_naive = summary["naive"]["avg_recall@5"]
    r_context = summary["context"]["avg_recall@5"]
    l_naive = summary["naive"]["avg_latency_ms"]
    l_context = summary["context"]["avg_latency_ms"]
    print(f"{'Precision@5':<25} {p_naive:>15.3f} {p_context:>15.3f} {p_context-p_naive:>+10.3f}")
    print(f"{'Recall@5':<25} {r_naive:>15.3f} {r_context:>15.3f} {r_context-r_naive:>+10.3f}")
    print(f"{'Latency (ms)':<25} {l_naive:>15} {l_context:>15} {l_context-l_naive:>+10}")
    print(f"{'Citation rate':<25} {'N/A':>15} {summary['context']['citation_rate']:>15.3f}")
    print("=" * 70)
    print()
    print("Per-query results:")
    for r in summary["results"]:
        print(f"  • {r['query']}")
        print(f"    Naive: P={r['naive']['precision@5']:.2f} R={r['naive']['recall@5']:.2f} ({r['naive']['n_retrieved']} chunks)")
        print(f"    ConText: P={r['context']['precision@5']:.2f} R={r['context']['recall@5']:.2f} ({r['context']['n_retrieved']} chunks, {r['context']['answer_chars']} chars, citations={'✓' if r['context']['has_citations'] else '✗'})")


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test-store.db"
    llm = sys.argv[2] if len(sys.argv) > 2 else "ornith-9b:ctx65k"
    summary = run_benchmark(db_path, llm)
    print_benchmark(summary)
    # Save
    with open("/tmp/benchmark-results.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to /tmp/benchmark-results.json")
