"""Proxy generation — ffmpeg wrapper for creating proxy files."""

from __future__ import annotations

import subprocess
from pathlib import Path


class ProxyGenerator:
    """Generates proxy files for fast preview and search."""

    # Default proxy settings (720p, 15fps)
    DEFAULT_WIDTH = 720
    DEFAULT_FPS = 15
    DEFAULT_CRF = 28
    DEFAULT_PRESET = "fast"

    def __init__(self, proxy_dir: str):
        self.proxy_dir = Path(proxy_dir)
        self.proxy_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        source_path: str | Path,
        width: int = DEFAULT_WIDTH,
        fps: int = DEFAULT_FPS,
        crf: int = DEFAULT_CRF,
        preset: str = DEFAULT_PRESET,
    ) -> Path:
        """Generate a proxy file from a source video."""
        source_path = Path(source_path)
        proxy_name = f"{source_path.stem}_proxy.mp4"
        proxy_path = self.proxy_dir / proxy_name

        if proxy_path.exists():
            return proxy_path

        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(source_path),
                "-vf", f"scale={width}:trunc(ow/a/2)*2",  # maintain aspect ratio
                "-r", str(fps),
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart",
                str(proxy_path),
            ],
            check=True, capture_output=True, text=True,
        )
        return proxy_path

    def delete(self, source_path: str | Path) -> None:
        """Delete the proxy file for a source."""
        source_path = Path(source_path)
        proxy_name = f"{source_path.stem}_proxy.mp4"
        proxy_path = self.proxy_dir / proxy_name
        if proxy_path.exists():
            proxy_path.unlink()

    def list_proxies(self) -> list[Path]:
        """List all generated proxy files."""
        return sorted(self.proxy_dir.glob("*_proxy.mp4"))
