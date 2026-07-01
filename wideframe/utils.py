"""Utility helpers for Wideframe."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def get_clip_by_path(db_path: str, file_path: str) -> dict[str, Any] | None:
    """Look up a clip in the database by file path."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT * FROM clips WHERE path = ?", (file_path,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    columns = [desc[0] for desc in cursor.description]
    data = dict(zip(columns, row))

    # Parse JSON fields
    for json_field in ("analysis", "transcript", "key_moments", "embeddings"):
        if data.get(json_field):
            try:
                data[json_field] = json.loads(data[json_field])
            except (json.JSONDecodeError, TypeError):
                pass

    return data


def get_all_clips(db_path: str, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Get all clips from the database with pagination."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT * FROM clips ORDER BY quality_score DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = cursor.fetchall()
    conn.close()

    columns = [desc[0] for desc in cursor.description]
    results = []
    for row in rows:
        data = dict(zip(columns, row))
        for json_field in ("analysis", "transcript", "key_moments", "embeddings"):
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        results.append(data)

    return results


def get_clip_count(db_path: str) -> int:
    """Get total number of indexed clips."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM clips")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def ensure_ffmpeg() -> bool:
    """Check if ffmpeg is available on the system."""
    import shutil
    return shutil.which("ffmpeg") is not None


def ensure_ffprobe() -> bool:
    """Check if ffprobe is available on the system."""
    import shutil
    return shutil.which("ffprobe") is not None
