"""
Example: Build a documentation Q&A bot in 5 minutes.

This script:
1. Indexes the Python standard library docs
2. Queries a few common questions
3. Prints the answers with source citations

Run: python examples/docs_qa_bot.py
"""

from context_engineer import ConText


def main():
    # 1. Initialize
    print("Initializing ConText...")
    ctx = ConText(
        db_path=".context/docs-qa.db",
        llm_model="llama3.2",
        embed_model="nomic-embed-text",
        context_window=8192,
    )

    # 2. Index (skip if already indexed)
    if ctx.stats()["documents"] == 0:
        print("Indexing docs/ ...")
        stats = ctx.build("./docs")
        print(f"Indexed {stats['files']} files, {stats['chunks']} chunks")
    else:
        print(f"Already have {ctx.stats()['documents']} documents indexed.")

    # 3. Query
    questions = [
        "What guarantees memory safety in Rust?",
        "How does Go handle concurrency?",
        "What is the Zen of Python?",
    ]

    for q in questions:
        print(f"\n{'=' * 60}")
        print(f"Q: {q}")
        print(f"{'=' * 60}")
        answer = ctx.query(q)
        print(f"\nA: {answer.text}")
        print(f"\nSources ({len(answer.sources)}):")
        for i, s in enumerate(answer.sources[:3], start=1):
            print(f"  [{i}] {s.source_path} (score: {s.score:.3f})")
        print(f"\nLatency: {answer.latency_ms}ms, "
              f"Tokens: {answer.prompt_tokens}+{answer.completion_tokens}")


if __name__ == "__main__":
    main()
