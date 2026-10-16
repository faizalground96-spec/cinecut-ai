"""Tahap 1 — Input Film: validasi file + baca metadata via ffprobe."""
from __future__ import annotations

from pathlib import Path

from ..utils import ffmpeg_helper
from ..utils.logger import Logger

ALLOWED_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


def ingest(input_path: str | Path, logger: Logger | None = None) -> dict:
    log = logger or Logger()
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"File film tidak ketemu: {path}")
    if path.suffix.lower() not in ALLOWED_EXT:
        raise ValueError(
            f"Format {path.suffix} belum didukung. Pakai: {', '.join(sorted(ALLOWED_EXT))}")
    info = ffmpeg_helper.media_info(path)
    if info["duration"] <= 0:
        raise ValueError("ffprobe tidak bisa membaca durasi file ini. File mungkin rusak.")
    log.log(f"Film masuk: {path.name} — durasi {info['duration']:.1f} detik, "
            f"{info['width']}x{info['height']} @ {info['fps']:.1f} fps, "
            f"audio: {len(info['audio_tracks'])} track, "
            f"subtitle: {len(info['subtitle_tracks'])} track")
    return {"path": str(path), **info}
