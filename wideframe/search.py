"""Semantic search across indexed footage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from wideframe.workspace import load_workspace, get_workspace_config


class Searcher:
    """Search indexed clips by semantic query."""

    def __init__(self, workspace_name: str | None = None):
        self.ws = load_workspace(workspace_name)
        config = get_workspace_config(self.ws)
        self.ai_model = config.get("ai_model", "gemini")

    def search(
        self,
        query: str,
        top_k: int = 20,
        min_quality: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search indexed footage by meaning (semantic search)."""
        conn = sqlite3.connect(self.ws.index_path)

        # 1. Get all clips with embeddings
        cursor = conn.execute("""
            SELECT path, duration, quality_score, analysis, key_moments, embeddings
            FROM clips
            WHERE quality_score >= ?
            ORDER BY quality_score DESC
        """, (min_quality,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # 2. Embed the query
        query_embedding = self._embed(query)
        if not query_embedding:
            # Fallback: just return top clips by quality
            return self._fallback_search(rows, top_k)

        # 3. Compute cosine similarity and rank
        results = []
        query_vec = np.array(query_embedding)

        for row in rows:
            path, duration, quality_score, analysis_str, key_moments_str, embeddings_str = row

            if not embeddings_str:
                continue

            clip_vec = np.array(json.loads(embeddings_str))

            # Cosine similarity
            norm_query = np.linalg.norm(query_vec)
            norm_clip = np.linalg.norm(clip_vec)

            if norm_query == 0 or norm_clip == 0:
                continue

            similarity = float(np.dot(query_vec, clip_vec) / (norm_query * norm_clip))

            results.append({
                "path": path,
                "duration": duration,
                "quality_score": quality_score,
                "similarity": similarity,
                "analysis": json.loads(analysis_str) if analysis_str else {},
                "key_moments": json.loads(key_moments_str) if key_moments_str else [],
                "combined_score": 0.6 * similarity + 0.4 * (quality_score / 100.0),
            })

        # 4. Sort by combined score and return top K
        results.sort(key=lambda r: r["combined_score"], reverse=True)
        return results[:top_k]

    def _embed(self, text: str) -> list[float]:
        """Generate embedding for search query."""
        if self.ai_model == "gemini":
            return self._embed_gemini(text)
        return []

    def _embed_gemini(self, text: str) -> list[float]:
        """Generate embedding using Gemini API."""
        try:
            import google.generativeai as genai

            api_key = __import__("os").environ.get("GOOGLE_API_KEY")
            if not api_key:
                return []

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("models/text-embedding-004")

            result = model.embed_content(content=text)
            return result.get("embedding", [])
        except Exception:
            return []

    def _fallback_search(self, rows: list[tuple], top_k: int) -> list[dict[str, Any]]:
        """Fallback when embeddings aren't available — return by quality."""
        results = []
        for row in rows:
            path, duration, quality_score, analysis_str, key_moments_str, _ = row
            results.append({
                "path": path,
                "duration": duration,
                "quality_score": quality_score,
                "similarity": 0.0,
                "analysis": json.loads(analysis_str) if analysis_str else {},
                "key_moments": json.loads(key_moments_str) if key_moments_str else [],
                "combined_score": quality_score / 100.0,
            })
        results.sort(key=lambda r: r["combined_score"], reverse=True)
        return results[:top_k]
