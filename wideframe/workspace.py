"""Workspace management — initialization, listing, loading."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from wideframe.models import Workspace

PROJECT_DIR = Path.home() / "Projects" / "wideframe-clone" / "workspaces"


def create_workspace(
    name: str,
    media_path: str,
    project_dir: str | None = None,
    ai_model: str = "gemini",
    transcriber: str = "assemblyai",
) -> Workspace:
    """Create a new workspace with proper directory structure."""
    if project_dir is None:
        project_dir = str(PROJECT_DIR)

    workspace_root = Path(project_dir) / name
    workspace_root.mkdir(parents=True, exist_ok=True)

    index_path = str(workspace_root / "index.db")
    proxy_path = str(workspace_root / "proxies")
    (Path(proxy_path)).mkdir(parents=True, exist_ok=True)
    (workspace_root / "sequences").mkdir(parents=True, exist_ok=True)
    (workspace_root / "exports").mkdir(parents=True, exist_ok=True)

    ws = Workspace(
        name=name,
        media_path=Path(media_path).resolve().as_posix(),
        index_path=index_path,
        proxy_path=proxy_path,
        created_at=__import__("datetime").datetime.now().isoformat(),
        ai_model=ai_model,
        transcriber=transcriber,
    )
    ws.save()
    _init_db(ws)
    return ws


def _init_db(ws: Workspace) -> None:
    """Initialize SQLite database with schema."""
    conn = sqlite3.connect(ws.index_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            duration REAL NOT NULL,
            resolution TEXT,
            fps REAL,
            file_size INTEGER,
            format TEXT,
            codec TEXT,
            analysis TEXT,
            transcript TEXT,
            quality_score REAL DEFAULT 0,
            embeddings TEXT,
            key_moments TEXT,
            indexed_at TEXT,
            proxy_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_clips_path ON clips(path);
        CREATE INDEX IF NOT EXISTS idx_clips_quality ON clips(quality_score);
        CREATE INDEX IF NOT EXISTS idx_clips_duration ON clips(duration);

        CREATE TABLE IF NOT EXISTS workspace_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)

    # Store workspace config
    conn.execute(
        "INSERT OR REPLACE INTO workspace_meta (key, value) VALUES ('ai_model', ?)",
        (getattr(ws, 'ai_model', 'gemini'),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO workspace_meta (key, value) VALUES ('transcriber', ?)",
        (getattr(ws, 'transcriber', 'assemblyai'),),
    )
    conn.commit()
    conn.close()


def load_workspace(workspace_name: str | None = None) -> Workspace:
    """Load a workspace by name."""
    if workspace_name is None:
        workspaces = list_workspaces()
        if not workspaces:
            raise FileNotFoundError("No workspaces found. Run 'wideframe init' first.")
        workspace_name = workspaces[0]

    ws_path = PROJECT_DIR / workspace_name
    if not ws_path.exists():
        # Try relative to CWD
        ws_path = Path(workspace_name)

    if not (ws_path / "workspace.json").exists():
        raise FileNotFoundError(f"Workspace '{workspace_name}' not found at {ws_path}")

    data = json.loads((ws_path / "workspace.json").read_text())
    ws = Workspace(
        name=data["name"],
        media_path=data["media_path"],
        index_path=data["index_path"],
        proxy_path=data["proxy_path"],
        created_at=data.get("created_at", ""),
        ai_model=data.get("ai_model", "gemini"),
        transcriber=data.get("transcriber", "assemblyai"),
    )

    # Load sequences
    seq_dir = ws_path / "sequences"
    if seq_dir.exists():
        for seq_file in seq_dir.glob("*.json"):
            from wideframe.models import Sequence
            ws.sequences.append(Sequence.from_dict(json.loads(seq_file.read_text())))

    return ws


def list_workspaces() -> list[str]:
    """List all available workspace names."""
    if not PROJECT_DIR.exists():
        return []
    return sorted([d.name for d in PROJECT_DIR.iterdir() if d.is_dir()])


def get_workspace_config(ws: Workspace) -> dict[str, str]:
    """Get AI/transcriber config from the workspace database."""
    conn = sqlite3.connect(ws.index_path)
    cursor = conn.execute("SELECT key, value FROM workspace_meta")
    config = dict(cursor.fetchall())
    conn.close()
    return config
