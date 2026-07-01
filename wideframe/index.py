"""Media indexing — scan, analyze, transcribe, embed."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from tqdm import tqdm

from wideframe.models import Clip
from wideframe.workspace import load_workspace, get_workspace_config

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mxf", ".avi", ".mkv", ".webm", ".ts"}


class Indexer:
    """Indexes video files: extracts metadata, analyzes content, transcribes, embeds."""

    def __init__(self, workspace_name: str | None = None):
        self.ws = load_workspace(workspace_name)
        config = get_workspace_config(self.ws)
        self.ai_model = config.get("ai_model", "gemini")
        self.transcriber = config.get("transcriber", "assemblyai")

    # ------------------------------------------------------------------
    # Scan media
    # ------------------------------------------------------------------

    def scan(self) -> list[Path]:
        """Scan the media folder for video files."""
        media_dir = Path(self.ws.media_path)
        if not media_dir.exists():
            raise FileNotFoundError(f"Media path does not exist: {media_dir}")

        videos = []
        for ext in SUPPORTED_EXTENSIONS:
            videos.extend(media_dir.rglob(f"*{ext}"))
        return sorted(videos)

    # ------------------------------------------------------------------
    # Metadata extraction (ffprobe)
    # ------------------------------------------------------------------

    def _get_metadata(self, path: Path) -> dict[str, Any]:
        """Extract video metadata using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(path),
                ],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)

            # Find video stream
            video_stream = None
            audio_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and audio_stream is None:
                    audio_stream = stream

            resolution = (0, 0)
            fps = 0.0
            duration = 0.0
            codec = ""

            if video_stream:
                w = video_stream.get("width", 0)
                h = video_stream.get("height", 0)
                resolution = (w, h)
                # Parse framerate
                fps_str = video_stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den) if float(den) != 0 else 0.0
                else:
                    fps = float(fps_str)
                codec = video_stream.get("codec_name", "")

            # Duration from format
            format_data = data.get("format", {})
            duration = float(format_data.get("duration", 0))

            return {
                "resolution": resolution,
                "fps": fps,
                "duration": duration,
                "codec": codec,
                "file_size": path.stat().st_size,
                "format": format_data.get("format_name", ""),
            }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            print(f"  [yellow]Warning: Could not extract metadata from {path}: {e}[/]", file=sys.stderr)
            return {
                "resolution": (0, 0),
                "fps": 0.0,
                "duration": 0.0,
                "codec": "",
                "file_size": 0,
                "format": "",
            }

    # ------------------------------------------------------------------
    # Proxy generation (ffmpeg)
    # ------------------------------------------------------------------

    def _generate_proxy(self, source_path: Path) -> str | None:
        """Generate a low-res proxy for fast preview/search."""
        proxy_dir = Path(self.ws.proxy_path)
        proxy_dir.mkdir(parents=True, exist_ok=True)

        proxy_name = f"{source_path.stem}_proxy.mp4"
        proxy_path = proxy_dir / proxy_name

        if proxy_path.exists():
            return str(proxy_path)

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(source_path),
                    "-vf", "scale=720:trunc(ow/a/2)*2",  # 720p, keep aspect ratio
                    "-r", "15",  # 15fps for preview
                    "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                    "-c:a", "aac", "-b:a", "64k",
                    "-movflags", "+faststart",
                    str(proxy_path),
                ],
                capture_output=True, text=True, timeout=300,
            )
            return str(proxy_path)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            print(f"  [yellow]Warning: Proxy generation failed for {source_path}: {e}[/]", file=sys.stderr)
            return None

    # ------------------------------------------------------------------
    # Content analysis (Gemini / CLIP)
    # ------------------------------------------------------------------

    def _analyze_content(self, proxy_path: str | Path) -> dict[str, Any]:
        """Analyze video content using Gemini vision API."""
        if self.ai_model == "gemini":
            return self._analyze_gemini(proxy_path)
        elif self.ai_model in ("clip", "blip"):
            return self._analyze_local(proxy_path)
        return {}

    def _analyze_gemini(self, proxy_path: str | Path) -> dict[str, Any]:
        """Use Google Gemini to describe scenes and key moments."""
        try:
            import google.generativeai as genai

            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                print("  [yellow]GOOGLE_API_KEY not set. Skipping Gemini analysis.[/]")
                return {}

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            # Take a few frames from the proxy for analysis
            frames = self._extract_frames(str(proxy_path), num_frames=5)

            if not frames:
                return {}

            # Analyze first frame for overall description
            with open(frames[0], "rb") as f:
                image_data = f.read()

            response = model.generate_content([
                "Describe this video frame. Include: scene type, people, objects, lighting, mood, camera angle. "
                "Also identify any key visual moments or noteworthy elements.",
                genai.protos.Part(image_data=image_data),
            ])

            description = response.text if hasattr(response, "text") else str(response)

            return {
                "description": description,
                "model": "gemini",
                "frames_analyzed": len(frames),
            }
        except Exception as e:
            print(f"  [yellow]Gemini analysis failed: {e}[/]", file=sys.stderr)
            return {"error": str(e)}

    def _analyze_local(self, proxy_path: str | Path) -> dict[str, Any]:
        """Use local CLIP/BLIP for content analysis."""
        # Placeholder — would use CLIP or BLIP model
        # This is a stub for the local fallback path
        return {"description": "Local analysis not yet implemented", "model": self.ai_model}

    def _extract_frames(self, video_path: str, num_frames: int = 5) -> list[str]:
        """Extract evenly-spaced frames from a video."""
        frames_dir = Path(self.ws.proxy_path) / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Get duration
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(video_path)],
                capture_output=True, text=True, timeout=15,
            )
            duration = float(result.stdout.strip())

            # Extract frames at even intervals
            frame_paths = []
            for i in range(num_frames):
                ts = (duration / (num_frames + 1)) * (i + 1)
                frame_path = frames_dir / f"frame_{i:04d}.jpg"
                if not frame_path.exists():
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                         "-vframes", "1", "-q:v", "2", str(frame_path)],
                        capture_output=True, timeout=30,
                    )
                if frame_path.exists():
                    frame_paths.append(str(frame_path))

            return frame_paths
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def _transcribe(self, source_path: Path, proxy_path: str | None) -> dict[str, Any]:
        """Transcribe audio from video file."""
        # Use proxy for transcription (faster)
        audio_source = proxy_path if proxy_path else str(source_path)

        if self.transcriber == "assemblyai":
            return self._transcribe_assemblyai(audio_source)
        elif self.transcriber == "whisper":
            return self._transcribe_whisper(audio_source)
        return {}

    def _transcribe_assemblyai(self, audio_source: str) -> dict[str, Any]:
        """Transcribe using AssemblyAI API."""
        try:
            import assemblyai as aai

            api_key = os.environ.get("ASSEMBLYAI_API_KEY")
            if not api_key:
                print("  [yellow]ASSEMBLYAI_API_KEY not set. Skipping transcription.[/]")
                return {}

            aai.config.api_key = api_key
            transcriber = aai.Transcriber()

            transcript = transcriber.transcode(audio_source)

            # Extract word-level timestamps
            words = []
            if hasattr(transcript, "words"):
                for w in transcript.words:
                    words.append({
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence,
                    })

            return {
                "text": transcript.text if hasattr(transcript, "text") else "",
                "words": words,
                "model": "assemblyai",
            }
        except Exception as e:
            print(f"  [yellow]AssemblyAI transcription failed: {e}[/]", file=sys.stderr)
            return {"error": str(e)}

    def _transcribe_whisper(self, audio_source: str) -> dict[str, Any]:
        """Transcribe using OpenAI Whisper (local or API)."""
        try:
            import openai

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("  [yellow]OPENAI_API_KEY not set. Skipping Whisper transcription.[/]")
                return {}

            client = openai.OpenAI(api_key=api_key)

            with open(audio_source, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="verbose_json"
                )

            return {
                "text": transcript.text,
                "words": [],  # Whisper verbose JSON has word segments
                "model": "whisper",
            }
        except Exception as e:
            print(f"  [yellow]Whisper transcription failed: {e}[/]", file=sys.stderr)
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Generate vector embedding for semantic search."""
        # Use the same model configured for the workspace
        if self.ai_model == "gemini":
            return self._embed_gemini(text)
        return []

    def _embed_gemini(self, text: str) -> list[float]:
        """Generate embedding using Gemini API."""
        try:
            import google.generativeai as genai

            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                return []

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("models/text-embedding-004")

            result = model.embed_content(content=text)
            return result.get("embedding", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Quality scoring (placeholder)
    # ------------------------------------------------------------------

    def _score_quality(self, metadata: dict[str, Any]) -> float:
        """Score clip quality on a 0-100 scale."""
        # Placeholder implementation — would analyze focus, lighting, stability
        score = 50.0  # default neutral score

        # Bonus for higher resolution
        w, h = metadata.get("resolution", (0, 0))
        if w >= 3840:  # 4K
            score += 20
        elif w >= 1920:  # 1080p
            score += 10

        # Bonus for higher frame rate
        fps = metadata.get("fps", 0)
        if fps >= 60:
            score += 10
        elif fps >= 30:
            score += 5

        return min(score, 100.0)

    # ------------------------------------------------------------------
    # Main index function
    # ------------------------------------------------------------------

    def index(
        self,
        all: bool = True,
        file_path: str | None = None,
        skip_proxy: bool = False,
        skip_transcript: bool = False,
    ) -> int:
        """Index video files and store in SQLite."""
        if file_path:
            paths = [Path(file_path)]
        elif all:
            paths = self.scan()
        else:
            print("Specify --all or --file.")
            return 0

        if not paths:
            print("No video files found.")
            return 0

        conn = sqlite3.connect(self.ws.index_path)
        count = 0

        for video_path in tqdm(paths, desc="Indexing"):
            try:
                # 1. Extract metadata
                metadata = self._get_metadata(video_path)

                # 2. Generate proxy (optional)
                proxy_path = None
                if not skip_proxy:
                    proxy_path = self._generate_proxy(video_path)

                # 3. Content analysis (via proxy if available)
                analysis = {}
                if proxy_path:
                    analysis = self._analyze_content(proxy_path)

                # 4. Transcription (optional)
                transcript = {}
                if not skip_transcript:
                    transcript = self._transcribe(video_path, proxy_path)

                # 5. Quality score
                quality = self._score_quality(metadata)

                # 6. Embeddings (from analysis description)
                embeddings = []
                desc = analysis.get("description", "")
                if desc:
                    embeddings = self._embed(desc)

                # 7. Key moments (from transcript words with high confidence)
                key_moments = []
                words = transcript.get("words", [])
                if words:
                    # Mark segments with high confidence as key moments
                    for w in words:
                        if w.get("confidence", 0) > 0.8:
                            key_moments.append({
                                "timestamp": w["start"] / 1000.0,  # ms → seconds
                                "type": "high-confidence-speech",
                                "text": w["word"],
                            })

                # 8. Insert into DB
                now = __import__("datetime").datetime.now().isoformat()
                conn.execute(
                    """INSERT OR REPLACE INTO clips (
                        path, duration, resolution, fps, file_size, format, codec,
                        analysis, transcript, quality_score, embeddings, key_moments,
                        indexed_at, proxy_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(video_path),
                        metadata["duration"],
                        json.dumps(metadata["resolution"]),
                        metadata["fps"],
                        metadata["file_size"],
                        metadata["format"],
                        metadata["codec"],
                        json.dumps(analysis),
                        json.dumps(transcript),
                        quality,
                        json.dumps(embeddings),
                        json.dumps(key_moments),
                        now,
                        proxy_path,
                    ),
                )
                count += 1

            except Exception as e:
                print(f"  [red]Error indexing {video_path}: {e}[/]", file=sys.stderr)

        conn.commit()
        conn.close()
        return count
