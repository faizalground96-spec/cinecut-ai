"""Tahap 4 — Pemotongan Klip Video (Pre-Cut Scenes).

FFmpeg memotong film asli per klip (re-encode, presisi). Subtitle bawaan
tidak ikut (softsub dibuang — tidak di-map). Suara asli film disimpan
dengan volume rendah sebagai ambiens (-25 dB, sesuai plan) atau dibungkam.
"""
from __future__ import annotations

from pathlib import Path

from ..utils import ffmpeg_helper
from ..utils.logger import Logger
from ..utils.time_parser import srt_to_seconds


def cut_clips(video_path: str, clips: list[dict], work_dir: str | Path,
              keep_ambient_db: float = -25.0,
              logger: Logger | None = None) -> list[dict]:
    log = logger or Logger()
    clip_dir = Path(work_dir) / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for c in clips:
        start = srt_to_seconds(c["start_time"])
        end = srt_to_seconds(c["end_time"])
        dest = clip_dir / f"clip_{c['clip_id']:03d}.mp4"
        # -ss sebelum -i = potong cepat & akurat; re-encode video,
        # audio asli dilemahkan jadi ambiens.
        cmd = [
            ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video_path),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-af", f"volume={keep_ambient_db}dB",
            "-c:a", "aac", "-movflags", "+faststart", str(dest),
        ]
        res = ffmpeg_helper.run_cmd(cmd, timeout=600)
        if res.returncode != 0:
            log.warn(f"Klip {c['clip_id']} gagal dipotong: {res.stderr[:300]}")
            continue
        item = dict(c)
        item["file"] = str(dest)
        item["duration"] = round(end - start, 3)
        out.append(item)
        log.log(f"Klip {c['clip_id']} ({item['duration']} dtk) -> {dest.name}")
    if not out:
        raise RuntimeError("Semua klip gagal dipotong. Cek file film & FFmpeg.")
    return out
