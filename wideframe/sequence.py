"""Sequence assembly — create and export timelines."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from wideframe.models import Sequence, SequenceClip, Transition
from wideframe.workspace import load_workspace


class Sequencer:
    """Assembles and exports video sequences."""

    def __init__(self, workspace_name: str | None = None):
        self.ws = load_workspace(workspace_name)

    def assemble(
        self,
        name: str,
        clip_indices: list[int] | None = None,
    ) -> Sequence:
        """Assemble a sequence from indexed clips."""
        conn = sqlite3.connect(self.ws.index_path)

        # Get all clips ordered by quality (or use specified indices)
        if clip_indices:
            placeholders = ",".join("?" for _ in clip_indices)
            cursor = conn.execute(f"""
                SELECT path, duration, quality_score, analysis, key_moments
                FROM clips
                WHERE path IN (
                    SELECT path FROM clips ORDER BY quality_score DESC
                    LIMIT 999999
                )
                LIMIT 999999
            """)
            # Filter to specified indices (1-based, from the quality-ranked list)
            all_clips = cursor.fetchall()
            selected = [all_clips[i - 1] for i in clip_indices if 0 < i <= len(all_clips)]
        else:
            cursor = conn.execute("""
                SELECT path, duration, quality_score, analysis, key_moments
                FROM clips
                ORDER BY quality_score DESC
            """)
            selected = cursor.fetchall()

        conn.close()

        # Build sequence
        clips = []
        for i, row in enumerate(selected):
            path, duration, quality_score, _, _ = row
            clips.append(SequenceClip(
                clip_path=path,
                trim_start=0.0,
                trim_end=duration,
                scale=1.0,
                position=0,
                label="a-roll",
            ))

        seq = Sequence(
            name=name,
            clips=clips,
            transitions=[],
            export_format="mp4",
            created_at=datetime.now().isoformat(),
            workspace_name=self.ws.name,
        )

        # Save sequence
        self._save_sequence(seq)
        return seq

    def _save_sequence(self, seq: Sequence) -> None:
        """Persist a sequence to disk."""
        seq_dir = Path(self.ws.index_path).parent / "sequences"
        seq_dir.mkdir(parents=True, exist_ok=True)
        path = seq_dir / f"{seq.name}.json"
        path.write_text(json.dumps(seq.to_dict(), indent=2))

    def export(
        self,
        sequence_name: str,
        export_format: str = "mp4",
        output_path: str | None = None,
   ) -> str:
        """Export a sequence as a video file using ffmpeg."""
        # Load the sequence
        seq_dir = Path(self.ws.index_path).parent / "sequences"
        seq_file = seq_dir / f"{sequence_name}.json"

        if not seq_file.exists():
            raise FileNotFoundError(f"Sequence '{sequence_name}' not found.")

        seq_data = json.loads(seq_file.read_text())
        seq = Sequence.from_dict(seq_data)

        if not seq.clips:
            raise ValueError("Sequence has no clips to export.")

        # Build ffmpeg command
        if output_path is None:
            exports_dir = Path(self.ws.index_path).parent / "exports"
            exports_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(exports_dir / f"{sequence_name}.{export_format}")

        # Build ffmpeg input arguments and filter complex
        input_args = []
        filter_parts = []
        stream_map = []

        for i, clip in enumerate(seq.clips):
            source = clip.clip_path

            # If source is a proxy, use it; otherwise use original
            if clip.proxy_path:
                source = clip.proxy_path

            input_args.extend(["-i", source])

            # Trim if specified
            if clip.trim_start > 0:
                filter_parts.append(f"[{i}:v]trim=start={clip.trim_start}[v{i}]")
                filter_parts.append(f"[{i}:a]atrim=start={clip.trim_start}[a{i}]")
            else:
                filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
                filter_parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

            stream_map.append(f"[v{i}]")
            stream_map.append(f"[a{i}]")

        # Concatenate all clips
        if len(seq.clips) > 1:
            video_inputs = "".join(f"[v{i}]" for i in range(len(seq.clips)))
            audio_inputs = "".join(f"[a{i}]" for i in range(len(seq.clips)))

            filter_parts.append(
                f"{video_inputs}concat=n={len(seq.clips)}:v=1:a=0[outv]"
            )
            filter_parts.append(
                f"{audio_inputs}concat=n={len(seq.clips)}:v=0:a=1[outa]"
            )

        filter_str = ";".join(filter_parts)
        filter_str += ",[outv],[outa]"

        # Build the full command
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_str])
        cmd.extend(["-map", "[outv]", "-map", "[outa]"])

        # Set output format settings
        if export_format == "mp4":
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18"])
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        elif export_format == "prores":
            cmd.extend(["-c:v", "prores", "-profile:v", "3"])
            cmd.extend(["-c:a", "pcm_s16le"])

        cmd.append(output_path)

        # Execute
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3600)
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            raise TimeoutError("Export timed out (1 hour limit).")
