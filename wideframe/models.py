"""Data models for Wideframe — Clip, Sequence, Workspace."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Clip
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    """Represents a single indexed video file."""

    path: str                            # absolute path to source file
    duration: float                      # seconds
    resolution: tuple[int, int] = (0, 0) # (width, height)
    fps: float = 0.0
    file_size: int = 0
    format: str = ""
    codec: str = ""

    # Analysis results
    analysis: dict[str, Any] = field(default_factory=dict)  # scene descriptions, key moments
    transcript: dict[str, Any] = field(default_factory=dict) # word-level timestamps
    quality_score: float = 0.0        # 0–100

    # Embeddings for semantic search
    embeddings: list[float] = field(default_factory=list)

    # Metadata
    indexed_at: str = ""              # ISO timestamp
    proxy_path: str = ""              # path to proxy file (if generated)

    # Key moments (timestamps of notable visual events)
    key_moments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Clip:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Clip:
        """Reconstruct from a DB row (JSON fields are strings)."""
        clip = cls(
            path=row["path"],
            duration=row["duration"],
            resolution=tuple(row["resolution"]) if row["resolution"] else (0, 0),
            fps=row["fps"],
            file_size=row["file_size"],
            format=row["format"],
            codec=row["codec"],
            quality_score=row["quality_score"],
            indexed_at=row["indexed_at"],
            proxy_path=row["proxy_path"],
        )
        # Parse JSON fields
        if row["analysis"]:
            clip.analysis = json.loads(row["analysis"])
        if row["transcript"]:
            clip.transcript = json.loads(row["transcript"])
        if row["key_moments"]:
            clip.key_moments = json.loads(row["key_moments"])
        if row["embeddings"]:
            clip.embeddings = list(json.loads(row["embeddings"]))
        return clip


# ---------------------------------------------------------------------------
# Sequence
# ---------------------------------------------------------------------------

@dataclass
class SequenceClip:
    """A clip placed in a sequence (with trim points)."""

    clip_path: str
    trim_start: float = 0.0    # offset into source clip (seconds)
    trim_end: float = 0.0      # end offset (0 = use full clip)
    scale: float = 1.0
    position: int = 0           # track position (V1=0, V2=1, ...)
    label: str = ""             # optional label (e.g., "a-roll", "b-roll")


@dataclass
class Transition:
    type: str = "cut"          # cut, crossfade, dissolve
    duration: float = 0.5      # seconds (for crossfade/dissolve)
    source_clip: int = 0
    target_clip: int = 0


@dataclass
class Sequence:
    name: str
    clips: list[SequenceClip] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    export_format: str = "mp4"
    created_at: str = ""
    workspace_name: str = ""

    def total_duration(self) -> float:
        """Approximate total duration of the sequence."""
        total = 0.0
        for clip in self.clips:
            end = clip.trim_end if clip.trim_end > 0 else 0.0
            clip_duration = end - clip.trim_start
            total += max(clip_duration, 0)
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "clips": [asdict(c) for c in self.clips],
            "transitions": [asdict(t) for t in self.transitions],
            "export_format": self.export_format,
            "created_at": self.created_at,
            "workspace_name": self.workspace_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Sequence:
        return cls(
            name=data["name"],
            clips=[SequenceClip.from_dict(c) for c in data["clips"]],
            transitions=[Transition.from_dict(t) for t in data["transitions"]],
            export_format=data.get("export_format", "mp4"),
            created_at=data.get("created_at", ""),
            workspace_name=data.get("workspace_name", ""),
        )


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

@dataclass
class Workspace:
    name: str
    media_path: str            # path to source media folder
    index_path: str            # path to SQLite index
    proxy_path: str            # path to proxy folder
    created_at: str = ""
    sequences: list[Sequence] = field(default_factory=list)

    @property
    def root(self) -> Path:
        return Path(self.index_path).parent

    @classmethod
    def create(
        cls,
        name: str,
        media_path: str,
        project_dir: str | None = None,
    ) -> Workspace:
        """Create a new workspace with proper directory structure."""
        if project_dir is None:
            project_dir = str(Path.home() / "Projects" / "wideframe-clone" / "workspaces")

        workspace_root = Path(project_dir) / name
        workspace_root.mkdir(parents=True, exist_ok=True)

        index_path = str(workspace_root / "index.db")
        proxy_path = str(workspace_root / "proxies")
        (Path(proxy_path)).mkdir(parents=True, exist_ok=True)

        # Create subdirectories for sequences
        (workspace_root / "sequences").mkdir(parents=True, exist_ok=True)

        return cls(
            name=name,
            media_path=Path(media_path).resolve().as_posix(),
            index_path=index_path,
            proxy_path=proxy_path,
            created_at=__import__("datetime").datetime.now().isoformat(),
        )

    def save_sequences(self) -> None:
        """Persist sequences to disk as JSON."""
        seq_dir = Path(self.index_path).parent / "sequences"
        seq_dir.mkdir(parents=True, exist_ok=True)
        for seq in self.sequences:
            path = seq_dir / f"{seq.name}.json"
            path.write_text(json.dumps(seq.to_dict(), indent=2))

    @classmethod
    def load(cls, workspace_dir: str) -> Workspace:
        """Load a workspace from disk."""
        ws_path = Path(workspace_dir)
        data = json.loads((ws_path / "workspace.json").read_text())
        ws = cls(
            name=data["name"],
            media_path=data["media_path"],
            index_path=data["index_path"],
            proxy_path=data["proxy_path"],
            created_at=data.get("created_at", ""),
        )
        # Load sequences
        seq_dir = ws_path / "sequences"
        if seq_dir.exists():
            for seq_file in seq_dir.glob("*.json"):
                ws.sequences.append(Sequence.from_dict(json.loads(seq_file.read_text())))
        return ws

    def save(self) -> None:
        """Persist workspace metadata."""
        data = {
            "name": self.name,
            "media_path": self.media_path,
            "index_path": self.index_path,
            "proxy_path": self.proxy_path,
            "created_at": self.created_at,
        }
        (Path(self.index_path).parent / "workspace.json").write_text(json.dumps(data, indent=2))
