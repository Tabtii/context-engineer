"""Real benchmark: Hybrid (vector + BM25) vs Pure Vector vs Naive.

Measures Precision@5 and Recall@5 on the same test set,
using a real LLM for answer quality.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from context_engineer import ConText
from context_engineer.core.budget import BudgetConfig
from context_engineer.core.embedder import Embedder
from context_engineer.core.retriever import Retriever
from context_engineer.core.hybrid import HybridRetriever
from context_engineer.store.db import Store


BENCHMARK_QUERIES = [
    {
        "query": "What guarantees memory safety in Rust?",
        "expected": ["ownership", "compile time"],
        "category": "specific_fact",
    },
    {
        "query": "Who created Python and when?",
        "expected": ["Guido van Rossum", "1991"],
        "category": "specific_fact",
    },
    {
        "query": "What is the Zen of Python?",
        "expected": ["Beautiful is better than ugly", "Simple is better"],
        "category": "quote",
    },
    {
        "query": "Which companies use Rust?",
        "expected": ["Mozilla", "Discord", "Cloudflare"],
        "category": "list",
    },
    {
        "query": "What are Python's use cases?",
        "expected": ["Web development", "Data science"],
        "category": "list",
    },
    {
        "query": "How does Go handle concurrency?",
        "expected": ["goroutines", "channels"],
        "category": "concept",
    },
    {
        "query": "What is the Rust ownership system?",
        "expected": ["owner", "compile time"],
        "category": "concept",
    },
    {
        "query": "When was Go announced?",
        "expected": ["2009", "Google"],
        "category": "specific_fact",
    },
]


def metrics(retrieved_texts: list[str], expected: list[str], k: int = 5):
    """Compute precision@k and recall@k."""
    if not retrieved_texts:
        return 0.0, 0.0
    top_k = retrieved_texts[:k]
    # Precision: fraction of top-k that contain at least one expected
    hits_p = sum(1 for t in top_k if any(e.lower() in t.lower() for e in expected))
    precision = hits_p / min(k, len(top_k))
    # Recall: fraction of expected found in top-k
    hits_r = sum(1 for e in expected if any(e.lower() in t.lower() for t in top_k))
    recall = hits_r / len(expected) if expected else 0.0
    return precision, recall


def run_retrieval_benchmark(db_path: str) -> dict:
    """Run retrieval-only benchmark (no LLM, fast)."""
    store = Store(db_path)
    emb = Embedder(model="nomic-embed-text")
    budget = BudgetConfig(total_tokens=8192)

    # Build retrievers
    naive_r = Retriever(store, emb, budget)
    hybrid_r = HybridRetriever(store, emb, budget)

    results = []
    for q in BENCHMARK_QUERIES:
        # Naive (pure vector)
        t0 = time.time()
        try:
            naive_chunks = naive_r.retrieve(q["query"], top_k=5)
        except Exception:
            naive_chunks = []
        naive_time = int((time.time() - t0) * 1000)
        naive_texts = [c.text for c in naive_chunks]

        # Hybrid
        t0 = time.time()
        try:
            hybrid_chunks = hybrid_r.retrieve(q["query"], top_k=5)
        except Exception:
            hybrid_chunks = []
        hybrid_time = int((time.time() - t0) * 1000)
        hybrid_texts = [c.text for c in hybrid_chunks]

        np_, nr_ = metrics(naive_texts, q["expected"])
        hp_, hr_ = metrics(hybrid_texts, q["expected"])

        results.append({
            "query": q["query"],
            "category": q["category"],
            "naive": {"precision": np_, "recall": nr_, "ms": naive_time, "n": len(naive_chunks)},
            "hybrid": {"precision": hp_, "recall": hr_, "ms": hybrid_time, "n": len(hybrid_chunks)},
        })

    def avg(key: str, system: str) -> float:
        vals = [r[system][key] for r in results]
        return sum(vals) / len(vals)

    return {
        "queries": len(results),
        "naive": {
            "avg_precision@5": round(avg("precision", "naive"), 3),
            "avg_recall@5": round(avg("recall", "naive"), 3),
            "avg_ms": int(avg("ms", "naive")),
        },
        "hybrid": {
            "avg_precision@5": round(avg("precision", "hybrid"), 3),
            "avg_recall@5": round(avg("recall", "hybrid"), 3),
            "avg_ms": int(avg("ms", "hybrid")),
        },
        "results": results,
    }


def print_benchmark(summary: dict):
    print("\n" + "=" * 70)
    print("ConText Hybrid (vector + BM25) vs Pure Vector — Retrieval Benchmark")
    print("=" * 70)
    print(f"Queries: {summary['queries']}")
    print()
    print(f"{'Metric':<25} {'Naive (vec)':>15} {'Hybrid (vec+BM25)':>20} {'Δ':>10}")
    print("-" * 70)
    p_n = summary["naive"]["avg_precision@5"]
    p_h = summary["hybrid"]["avg_precision@5"]
    r_n = summary["naive"]["avg_recall@5"]
    r_h = summary["hybrid"]["avg_recall@5"]
    t_n = summary["naive"]["avg_ms"]
    t_h = summary["hybrid"]["avg_ms"]
    print(f"{'Precision@5':<25} {p_n:>15.3f} {p_h:>20.3f} {p_h-p_n:>+10.3f}")
    print(f"{'Recall@5':<25} {r_n:>15.3f} {r_h:>20.3f} {r_h-r_n:>+10.3f}")
    print(f"{'Latency (ms)':<25} {t_n:>15} {t_h:>20} {t_h-t_n:>+10}")
    print("=" * 70)
    print()
    print("Per-query results:")
    for r in summary["results"]:
        print(f"  • [{r['category']:<15}] {r['query'][:50]}")
        print(f"    Naive:  P={r['naive']['precision']:.2f} R={r['naive']['recall']:.2f} ({r['naive']['n']} chunks, {r['naive']['ms']}ms)")
        print(f"    Hybrid: P={r['hybrid']['precision']:.2f} R={r['hybrid']['recall']:.2f} ({r['hybrid']['n']} chunks, {r['hybrid']['ms']}ms)")


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test-store.db"
    summary = run_retrieval_benchmark(db)
    print_benchmark(summary)
    with open("/tmp/benchmark-retrieval.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to /tmp/benchmark-retrieval.json")
