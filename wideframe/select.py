"""Clip selection — filter and rank indexed clips."""

from __future__ import annotations

import sqlite3
from typing import Any

from wideframe.workspace import load_workspace, get_workspace_config


class Selector:
    """Selects the best clips from indexed footage based on criteria."""

    def __init__(self, workspace_name: str | None = None):
        self.ws = load_workspace(workspace_name)

    def select(
        self,
        criteria: str = "",
        count: int = 50,
        clip_type: str = "",
        min_duration: float = 0.0,
        max_duration: float = 0.0,
        min_quality: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Select clips matching the given criteria."""
        conn = sqlite3.connect(self.ws.index_path)

        # Build query with filters
        conditions = ["quality_score >= ?", "duration >= ?"]
        params: list[Any] = [min_quality, min_duration]

        if max_duration > 0:
            conditions.append("duration <= ?")
            params.append(max_duration)

        if criteria:
            # Simple keyword matching in analysis text
            conditions.append("analysis LIKE ?")
            params.append(f"%{criteria}%")

        if clip_type:
            conditions.append("analysis LIKE ?")
            params.append(f"%{clip_type}%")

        where_clause = " AND ".join(conditions)

        cursor = conn.execute(f"""
            SELECT path, duration, quality_score, analysis, key_moments
            FROM clips
            WHERE {where_clause}
            ORDER BY quality_score DESC
        """, params)

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows[:count]:
            path, duration, quality_score, analysis_str, key_moments_str = row
            results.append({
                "path": path,
                "duration": duration,
                "quality_score": quality_score,
                "analysis": __import__("json").loads(analysis_str) if analysis_str else {},
                "key_moments": __import__("json").loads(key_moments_str) if key_moments_str else [],
            })

        return results
