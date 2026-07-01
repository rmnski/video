"""CLI entry point for Wideframe."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from wideframe import __version__

console = Console()


def _print_wideframe_banner() -> None:
    banner = f"""
[bold cyan]╔══════════════════════════════════════╗
║        W I D E F R A M E             ║
║  Open-source video pre-editing CLI   ║
║  v{__version__}                          ║
╚══════════════════════════════════════╝[/bold cyan]
    """
    console.print(banner)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(version=__version__, prog_name="wideframe")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Wideframe — AI-powered video pre-editing CLI."""
    _print_wideframe_banner()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@main.command()
@click.argument("name")
@click.option("--media-path", "-m", required=True, help="Path to source media folder.")
@click.option("--project-dir", "-p", default=None, help="Base project directory (default: ~/Projects/wideframe-clone/workspaces).")
@click.option("--ai-model", "-a", default="gemini", help="AI model for analysis (gemini, clip, blip). Default: gemini.")
@click.option("--transcriber", "-t", default="assemblyai", help="Transcription provider (assemblyai, whisper). Default: assemblyai.")
@click.pass_context
def init(ctx: click.Context, name: str, media_path: str, project_dir: str | None, ai_model: str, transcriber: str) -> None:
    """Initialize a new workspace."""
    from wideframe.workspace import create_workspace

    try:
        ws = create_workspace(name, media_path, project_dir, ai_model, transcriber)
        console.print(f"[green]✓[/] Workspace '{ws.name}' created at [bold]{ws.index_path}[/bold]")
        console.print(f"  Media: {ws.media_path}")
        console.print(f"  Proxies: {ws.proxy_path}")
        console.print(f"  AI Model: {ws.ai_model}")
        console.print(f"  Transcriber: {ws.transcriber}")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------

@main.command()
@click.argument("workspace", required=False)
@click.option("--workspace-name", "-w", default=None, help="Workspace name (if not using default).")
@click.option("--all", is_flag=True, default=False, help="Index all media in workspace.")
@click.option("--file", "-f", default=None, help="Index a specific file.")
@click.option("--skip-proxy", is_flag=True, default=False, help="Skip proxy generation.")
@click.option("--skip-transcript", is_flag=True, default=False, help="Skip transcription.")
@click.pass_context
def index(
    ctx: click.Context,
    workspace: str | None,
    workspace_name: str | None,
    all: bool,
    file: str | None,
    skip_proxy: bool,
    skip_transcript: bool,
) -> None:
    """Index media files — extract metadata, analyze, transcribe, embed."""
    from wideframe.index import Indexer
    from wideframe.workspace import load_workspace

    try:
        ws = load_workspace(workspace or workspace_name)
        indexer = Indexer(ws)

        console.print("[cyan]Indexing media...[/]")
        results = indexer.index(
            all=all,
            file_path=file,
            skip_proxy=skip_proxy,
            skip_transcript=skip_transcript,
        )
        console.print(f"[green]✓[/] Indexed {results} clip(s)")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@main.command()
@click.argument("query")
@click.option("--workspace-name", "-w", required=True, help="Workspace name.")
@click.option("--top-k", "-k", default=20, help="Number of results (default: 20).")
@click.option("--min-quality", default=0.0, help="Minimum quality score filter (0-100).")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    workspace_name: str,
    top_k: int,
    min_quality: float,
) -> None:
    """Search indexed footage by meaning (semantic search)."""
    from wideframe.search import Searcher
    from wideframe.workspace import load_workspace

    try:
        ws = load_workspace(workspace_name)
        searcher = Searcher(ws)
        results = searcher.search(query, top_k=top_k, min_quality=min_quality)

        if not results:
            console.print("[yellow]No results found.[/]")
            return

        console.print(f"[green]Found {len(results)} result(s) for: {query!r}[/]\n")
        for i, r in enumerate(results, 1):
            duration = f"{r['duration']:.1f}s"
            quality = f"{r['quality_score']:.0f}"
            console.print(f"  [bold]{i}.[/] {r['path']}")
            console.print(f"      Duration: {duration} | Quality: {quality}")
            if r.get("analysis"):
                console.print(f"      Analysis: {r['analysis'].get('description', 'N/A')[:100]}")
            if r.get("key_moments"):
                moments = r["key_moments"][:3]
                if moments:
                    console.print(f"      Key moments: {', '.join(str(m.get('timestamp', '?')) for m in moments)}...")
            console.print("")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# select
# ---------------------------------------------------------------------------

@main.command()
@click.option("--workspace-name", "-w", required=True, help="Workspace name.")
@click.option("--criteria", "-c", default="", help="Selection criteria (e.g. 'interview, clear audio').")
@click.option("--count", "-n", default=50, help="Max number of clips to select (default: 50).")
@click.option("--type", default="", help="Filter by type (a-roll, b-roll, interview).")
@click.option("--min-duration", default=0.0, help="Minimum clip duration in seconds.")
@click.option("--max-duration", default=0.0, help="Maximum clip duration in seconds (0 = unlimited).")
@click.option("--min-quality", default=0.0, help="Minimum quality score (0-100).")
@click.pass_context
def select(
    ctx: click.Context,
    workspace_name: str,
    criteria: str,
    count: int,
    type_filter: str,
    min_duration: float,
    max_duration: float,
    min_quality: float,
) -> None:
    """Select the best clips from indexed footage."""
    from wideframe.select import Selector
    from wideframe.workspace import load_workspace

    try:
        ws = load_workspace(workspace_name)
        selector = Selector(ws)
        results = selector.select(
            criteria=criteria,
            count=count,
            clip_type=type_filter,
            min_duration=min_duration,
            max_duration=max_duration,
            min_quality=min_quality,
        )

        console.print(f"[green]Selected {len(results)} clip(s)[/]\n")
        for i, r in enumerate(results, 1):
            console.print(f"  [bold]{i}.[/] {r['path']} ({r['duration']:.1f}s, quality: {r['quality_score']:.0f})")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

@main.command()
@click.argument("workspace_name")
@click.argument("sequence_name")
@click.option("--clips", "-c", default=None, help="Comma-separated list of clip indices to include.")
@click.pass_context
def assemble(
    ctx: click.Context,
    workspace_name: str,
    sequence_name: str,
    clips: str | None,
) -> None:
    """Assemble a sequence from selected clips."""
    from wideframe.sequence import Sequencer
    from wideframe.workspace import load_workspace

    try:
        ws = load_workspace(workspace_name)
        sequencer = Sequencer(ws)

        clip_indices = None
        if clips:
            clip_indices = [int(x.strip()) for x in clips.split(",")]

        seq = sequencer.assemble(sequence_name, clip_indices=clip_indices)
        console.print(f"[green]✓[/] Sequence '{seq.name}' created with {len(seq.clips)} clip(s)")
        console.print(f"  Total duration: {seq.total_duration():.1f}s")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@main.command()
@click.argument("workspace_name")
@click.argument("sequence_name")
@click.option("--format", "-f", default="mp4", help="Export format (mp4, prores, etc.). Default: mp4.")
@click.option("--output", "-o", default=None, help="Output path (default: workspace/exports/).")
@click.pass_context
def export(
    ctx: click.Context,
    workspace_name: str,
    sequence_name: str,
    format: str,
    output: str | None,
) -> None:
    """Export a sequence as video."""
    from wideframe.sequence import Sequencer
    from wideframe.workspace import load_workspace

    try:
        ws = load_workspace(workspace_name)
        sequencer = Sequencer(ws)
        export_path = sequencer.export(sequence_name, export_format=format, output_path=output)
        console.print(f"[green]✓[/] Exported to [bold]{export_path}[/bold]")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@main.command()
@click.option("--workspace-name", "-w", default=None, help="Show status for specific workspace.")
@click.pass_context
def status(ctx: click.Context, workspace_name: str | None) -> None:
    """Show workspace status and statistics."""
    from wideframe.workspace import list_workspaces

    workspaces = list_workspaces()
    if not workspaces:
        console.print("[yellow]No workspaces found.[/]")
        return

    for ws_name in workspaces:
        try:
            ws = load_workspace(ws_name)
            # Count clips in index
            import sqlite3
            conn = sqlite3.connect(ws.index_path)
            cursor = conn.execute("SELECT COUNT(*) FROM clips")
            clip_count = cursor.fetchone()[0]
            conn.close()

            console.print(f"\n[bold cyan]{ws.name}[/]")
            console.print(f"  Media: {ws.media_path}")
            console.print(f"  Clips indexed: {clip_count}")
            console.print(f"  Sequences: {len(ws.sequences)}")
        except Exception as e:
            console.print(f"[red]Error loading '{ws_name}': {e}[/]")
