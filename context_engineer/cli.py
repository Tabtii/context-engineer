"""ConText CLI.

Usage:
    context build <path>          Index documents
    context query "question"      Ask a question
    context stats                  Show database stats
    context list                   List indexed documents
    context remove <source>        Remove a document
    context serve                  Start HTTP API server
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from rich.table import Table

from context_engineer import ConText, __version__


console = Console()


def _get_context(ctx_obj) -> ConText:
    """Lazy-init ConText from Click context."""
    if "engine" not in ctx_obj:
        ctx_obj["engine"] = ConText(
            db_path=ctx_obj.get("db_path", ".context/store.db"),
            llm_model=ctx_obj.get("llm_model", "llama3.2"),
            embed_model=ctx_obj.get("embed_model", "nomic-embed-text"),
            ollama_url=ctx_obj.get("ollama_url", "http://localhost:11434"),
            context_window=ctx_obj.get("context_window", 8192),
        )
    return ctx_obj["engine"]


@click.group()
@click.option("--db", default=".context/store.db", help="Path to SQLite database")
@click.option("--llm", default="llama3.2", help="Ollama LLM model name")
@click.option("--embed", default="nomic-embed-text", help="Ollama embedding model name")
@click.option("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
@click.option("--context-window", default=8192, type=int, help="LLM context window in tokens")
@click.version_option(version=__version__, prog_name="context")
@click.pass_context
def main(ctx, db, llm, embed, ollama_url, context_window):
    """ConText — Context-Engineer for AI Agents."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db
    ctx.obj["llm_model"] = llm
    ctx.obj["embed_model"] = embed
    ctx.obj["ollama_url"] = ollama_url
    ctx.obj["context_window"] = context_window


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--pattern", default="*.{md,txt,py,js,ts,go,rs,java,c,cpp,h,hpp,json,yaml,yml}",
              help="File pattern to match (comma-separated)")
@click.option("--no-recursive", is_flag=True, help="Don't recurse into subdirectories")
@click.option("--max-size", default=5.0, type=float, help="Max file size in MB")
@click.pass_context
def build(ctx, path, pattern, no_recursive, max_size):
    """Index documents from PATH."""
    console.print(f"[bold cyan]ConText v{__version__}[/bold cyan] — Indexing [green]{path}[/green]")
    engine = _get_context(ctx.obj)
    stats = engine.build(
        path=path,
        recursive=not no_recursive,
        pattern=pattern,
        max_file_size_mb=max_size,
    )
    console.print(Panel(
        f"[green]✓ Indexed[/green] [bold]{stats['files']}[/bold] files\n"
        f"[green]✓ Created[/green] [bold]{stats['chunks']}[/bold] chunks\n"
        f"[yellow]⚠ Skipped[/yellow] [bold]{stats['skipped']}[/bold] files",
        title="Build Complete",
        border_style="green",
    ))


@main.command()
@click.argument("question")
@click.option("--top-k", default=20, type=int, help="Number of chunks to retrieve")
@click.option("--temperature", default=0.3, type=float, help="LLM temperature")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--no-citations", is_flag=True, help="Hide source citations")
@click.pass_context
def query(ctx, question, top_k, temperature, as_json, no_citations):
    """Ask a QUESTION and get a sourced answer."""
    engine = _get_context(ctx.obj)
    with console.status(f"[cyan]Searching and generating answer...[/cyan]"):
        answer = engine.query(question, top_k=top_k, temperature=temperature)
    if as_json:
        click.echo(json.dumps({
            "text": answer.text,
            "sources": [s.to_dict() for s in answer.sources],
            "tokens": {
                "prompt": answer.prompt_tokens,
                "completion": answer.completion_tokens,
            },
            "latency_ms": answer.latency_ms,
        }, indent=2, ensure_ascii=False))
        return
    # Pretty output
    console.print(Panel(
        answer.text,
        title=f"[bold green]Answer[/bold green]  ({answer.latency_ms}ms, {answer.prompt_tokens}+{answer.completion_tokens} tokens)",
        border_style="green",
    ))
    if answer.sources and not no_citations:
        table = Table(title="Sources", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Source", style="cyan")
        table.add_column("Strategy", style="magenta")
        table.add_column("Score", style="green", justify="right")
        table.add_column("Preview", style="dim")
        for i, s in enumerate(answer.sources, start=1):
            preview = s.text[:80].replace("\n", " ") + ("..." if len(s.text) > 80 else "")
            table.add_row(str(i), s.source_path, s.strategy, f"{s.score:.3f}", preview)
        console.print(table)


@main.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    engine = _get_context(ctx.obj)
    s = engine.stats()
    table = Table(title=f"ConText Database — {s['db_path']}", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Documents", str(s["documents"]))
    table.add_row("Chunks", str(s["chunks"]))
    table.add_row("Embeddings", str(s["embeddings"]))
    table.add_row("Queries logged", str(s["queries"]))
    table.add_row("DB size", f"{s['db_size_mb']} MB")
    table.add_row("LLM model", s["llm_model"])
    table.add_row("Embed model", s["embed_model"])
    table.add_row("Context window", f"{s['context_window']} tokens")
    table.add_row("Cache", f"{s['embedder']['size']}/{s['embedder']['max']}")
    if s.get("strategies"):
        table.add_section()
        table.add_row("[bold]Strategies[/bold]", "")
        for strat, count in s["strategies"].items():
            table.add_row(f"  {strat}", str(count))
    console.print(table)


@main.command("list")
@click.pass_context
def list_docs(ctx):
    """List all indexed documents."""
    engine = _get_context(ctx.obj)
    docs = engine.list_documents()
    if not docs:
        console.print("[yellow]No documents indexed yet.[/yellow]")
        console.print("Run: [cyan]context build <path>[/cyan]")
        return
    table = Table(title=f"Indexed Documents ({len(docs)})", show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Type", style="magenta")
    for d in docs:
        table.add_row(str(d["id"]), d["source"], d["type"])
    console.print(table)


@main.command()
@click.argument("source")
@click.pass_context
def remove(ctx, source):
    """Remove a document by source path."""
    engine = _get_context(ctx.obj)
    n = engine.remove(source)
    if n > 0:
        console.print(f"[green]✓ Removed[/green] {n} document(s) matching [cyan]{source}[/cyan]")
    else:
        console.print(f"[yellow]No documents matching[/yellow] {source}")


@main.command()
@click.option("--host", default="127.0.0.1", help="HTTP host")
@click.option("--port", default=8765, type=int, help="HTTP port")
@click.pass_context
def serve(ctx, host, port):
    """Start HTTP API server (MCP-compatible)."""
    from context_engineer.server import run_server
    engine = _get_context(ctx.obj)
    console.print(f"[bold cyan]ConText API[/bold cyan] serving on [green]http://{host}:{port}[/green]")
    console.print("Endpoints:")
    console.print("  POST /query   — [cyan]{\"question\": \"...\"}[/cyan]")
    console.print("  GET  /stats   — DB stats")
    console.print("  POST /build   — [cyan]{\"path\": \"...\"}[/cyan]")
    run_server(engine, host=host, port=port)


if __name__ == "__main__":
    main(obj={})
