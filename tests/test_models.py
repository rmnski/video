"""Tests for Wideframe data models."""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wideframe.models import Clip, Sequence, SequenceClip, Transition, Workspace


def test_clip_to_dict():
    clip = Clip(
        path="/tmp/test.mp4",
        duration=120.5,
        resolution=(1920, 1080),
        fps=30.0,
    )
    d = clip.to_dict()
    assert d["path"] == "/tmp/test.mp4"
    assert d["duration"] == 120.5
    assert d["resolution"] == (1920, 1080)


def test_clip_from_dict():
    data = {
        "path": "/tmp/test.mp4",
        "duration": 120.5,
        "resolution": [1920, 1080],
        "fps": 30.0,
        "file_size": 1000000,
        "format": "mov",
        "codec": "h264",
        "analysis": {},
        "transcript": {},
        "quality_score": 85.0,
        "embeddings": [0.1, 0.2, 0.3],
        "key_moments": [],
        "indexed_at": "2026-06-30T00:00:00",
        "proxy_path": "/tmp/test_proxy.mp4",
    }
    clip = Clip.from_dict(data)
    assert clip.path == "/tmp/test.mp4"
    assert clip.quality_score == 85.0


def test_clip_from_row():
    row = {
        "id": 1,
        "path": "/tmp/test.mp4",
        "duration": 120.5,
        "resolution": "[1920, 1080]",
        "fps": 30.0,
        "file_size": 1000000,
        "format": "mov",
        "codec": "h264",
        "analysis": json.dumps({"description": "test scene"}),
        "transcript": json.dumps({"text": "hello world"}),
        "quality_score": 85.0,
        "embeddings": json.dumps([0.1, 0.2]),
        "key_moments": json.dumps([{"timestamp": 10.0}]),
        "indexed_at": "2026-06-30T00:00:00",
        "proxy_path": "/tmp/test_proxy.mp4",
    }
    clip = Clip.from_row(row)
    assert clip.path == "/tmp/test.mp4"
    assert clip.analysis["description"] == "test scene"
    assert clip.transcript["text"] == "hello world"
    assert clip.embeddings == [0.1, 0.2]
    assert clip.key_moments == [{"timestamp": 10.0}]


def test_sequence_total_duration():
    seq = Sequence(
        name="test",
        clips=[
            SequenceClip(clip_path="/tmp/a.mp4", trim_start=0, trim_end=10),
            SequenceClip(clip_path="/tmp/b.mp4", trim_start=5, trim_end=15),
        ],
    )
    assert seq.total_duration() == 20.0


def test_workspace_create():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace.create(
            name="test-ws",
            media_path="/tmp/test-media",
            project_dir=tmpdir,
        )
        assert ws.name == "test-ws"
        assert ws.proxy_path.endswith("test-ws/proxies")
        assert Path(ws.index_path).parent.exists()
