"""Tests for clip selection (select.py)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from wideframe.select import Selector


def _create_test_db(db_path: str) -> None:
    """Create a test SQLite database with sample clip data."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE clips (
            path TEXT,
            duration REAL,
            quality_score REAL,
            analysis TEXT,
            key_moments TEXT
        )
    """)

    sample_clips = [
        (
            "/tmp/clip1.mp4", 10.0, 0.95,
            json.dumps({"description": "outdoor interview", "scene_type": "talking_head"}),
            json.dumps([{"timestamp": 2.0, "label": "speaker_start"}]),
        ),
        (
            "/tmp/clip2.mp4", 30.0, 0.70,
            json.dumps({"description": "aerial drone shot", "scene_type": "landscape"}),
            json.dumps([]),
        ),
        (
            "/tmp/clip3.mp4", 5.0, 0.40,
            json.dumps({"description": "close-up product shot", "scene_type": "product"}),
            json.dumps([{"timestamp": 1.0, "label": "logo_visible"}]),
        ),
        (
            "/tmp/clip4.mp4", 15.0, 0.85,
            json.dumps({"description": "crowd cheering", "scene_type": "outdoor"}),
            json.dumps([{"timestamp": 5.0, "label": "peak_energy"}]),
        ),
        (
            "/tmp/clip5.mp4", 2.0, 0.30,
            json.dumps({"description": "black screen fade", "scene_type": "transition"}),
            json.dumps([]),
        ),
    ]

    conn.executemany(
        "INSERT INTO clips (path, duration, quality_score, analysis, key_moments) VALUES (?, ?, ?, ?, ?)",
        sample_clips,
    )
    conn.commit()
    conn.close()


def _make_selector(tmpdir: str) -> tuple[Selector, str]:
    """Create a Selector pointing to a test workspace with a populated DB."""
    index_path = str(Path(tmpdir) / "test-ws" / "index.db")
    _create_test_db(index_path)

    ws_config = {
        "name": "test-ws",
        "media_path": "/tmp/test-media",
        "project_dir": tmpdir,
        "proxy_path": str(Path(tmpdir) / "test-ws" / "proxies"),
        "index_path": index_path,
    }

    with patch("wideframe.select.load_workspace") as mock_load:
        mock_load.return_value = type("MockWorkspace", (), ws_config)()
        sel = Selector(workspace_name="test-ws")

    return sel, index_path


def test_select_no_filters_returns_all_ordered_by_quality():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select()  # no filters

    assert len(results) == 5
    # Should be ordered by quality_score DESC
    scores = [r["quality_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["path"] == "/tmp/clip1.mp4"  # 0.95


def test_select_min_quality_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(min_quality=0.5)

    assert len(results) == 3
    for r in results:
        assert r["quality_score"] >= 0.5


def test_select_min_duration_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(min_duration=10.0)

    assert len(results) == 3  # 10s, 30s, 15s
    for r in results:
        assert r["duration"] >= 10.0


def test_select_max_duration_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(max_duration=12.0)

    assert len(results) == 2  # 10s, 5s
    for r in results:
        assert r["duration"] <= 12.0


def test_select_combined_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(
            min_quality=0.5,
            min_duration=10.0,
            max_duration=20.0,
        )

    assert len(results) == 2  # 10s (0.95) and 15s (0.85)
    for r in results:
        assert 0.5 <= r["quality_score"]
        assert 10.0 <= r["duration"] <= 20.0


def test_select_criteria_keyword_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(criteria="interview")

    assert len(results) == 1
    assert results[0]["path"] == "/tmp/clip1.mp4"


def test_select_clip_type_keyword_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(clip_type="product")

    assert len(results) == 1
    assert results[0]["path"] == "/tmp/clip3.mp4"


def test_select_count_limits_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(count=2)

    assert len(results) == 2


def test_select_parses_json_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(count=1)

    assert isinstance(results[0]["analysis"], dict)
    assert results[0]["analysis"]["description"] == "outdoor interview"
    assert isinstance(results[0]["key_moments"], list)
    assert results[0]["key_moments"][0]["label"] == "speaker_start"


def test_select_handles_empty_analysis():
    """Clips with NULL analysis should return empty dict/list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = sqlite3.connect(str(Path(tmpdir) / "test-ws" / "index.db"))
        conn.execute("INSERT INTO clips VALUES (?, ?, ?, NULL, NULL))",
                     ("/tmp/null_clip.mp4", 5.0, 0.6))
        conn.commit()
        conn.close()

        sel, _ = _make_selector(tmpdir)
        results = sel.select()

    null_clip = [r for r in results if r["path"] == "/tmp/null_clip.mp4"]
    assert len(null_clip) == 1
    assert null_clip[0]["analysis"] == {}
    assert null_clip[0]["key_moments"] == []


def test_select_no_matches():
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select(criteria="nonexistent_keyword_xyz")

    assert results == []


def test_select_default_count_50():
    """Default count should be 50 (more than our 5 sample clips)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sel, _ = _make_selector(tmpdir)
        results = sel.select()

    assert len(results) == 5  # all clips returned
