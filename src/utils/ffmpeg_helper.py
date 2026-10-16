"""Pembungkus FFmpeg / FFprobe + deteksi encoder GPU.

Mencari binary dengan urutan: folder bin/ di samping proyek (hasil
bundling Windows) -> PATH sistem. Di Windows .exe, bin/ffmpeg.exe dipakai.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def find_binary(name: str) -> str:
    """Cari ffmpeg / ffprobe. Kembalikan path atau nama (kalau di PATH)."""
    exe = name + (".exe" if _is_windows() else "")
    bundled = _project_root() / "bin" / exe
    if bundled.exists():
        return str(bundled)
    found = shutil.which(name)
    if found:
        return found
    return name  # biarkan subprocess memberi error yang jelas


def _is_windows() -> bool:
    import platform
    return platform.system().lower() == "windows"


def run_cmd(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Jalankan perintah. Kalau binary tidak ketemu (mis. FFmpeg belum
    terpasang / folder bin/ kosong), kembalikan returncode 1 dengan pesan
    jelas — JANGAN biarkan FileNotFoundError mentah meledak ke GUI."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, errors="replace")
    except FileNotFoundError as e:
        prog = cmd[0] if cmd else "program"
        return subprocess.CompletedProcess(
            cmd, 1, "",
            f"Program tidak ditemukan: {prog} ({e}). "
            "Pasang FFmpeg atau pastikan folder bin/ berisi ffmpeg.exe / ffprobe.exe.")


def probe(path: str | Path) -> dict:
    """Baca metadata file video lewat ffprobe (JSON)."""
    cmd = [find_binary("ffprobe"), "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    res = run_cmd(cmd, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe gagal untuk {path}: {res.stderr.strip()[:500]}")
    return json.loads(res.stdout or "{}")


def media_info(path: str | Path) -> dict:
    """Ringkas metadata: durasi, resolusi, fps, track audio/subtitle."""
    data = probe(path)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    fps = 0.0
    try:
        num, den = video.get("r_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps = 0.0
    return {
        "duration": float(fmt.get("duration", 0) or 0),
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": fps,
        "audio_tracks": [s for s in streams if s.get("codec_type") == "audio"],
        "subtitle_tracks": [s for s in streams if s.get("codec_type") == "subtitle"],
        "format_name": fmt.get("format_name", ""),
        "streams": streams,
    }


def available_encoders() -> set[str]:
    cmd = [find_binary("ffmpeg"), "-hide_banner", "-encoders"]
    res = run_cmd(cmd, timeout=60)
    out = res.stdout or ""
    found = set()
    for name in ("h264_nvenc", "h264_amf", "h264_qsv", "libx264"):
        if name in out:
            found.add(name)
    return found


def pick_h264_encoder() -> str:
    """Pilih encoder sesuai plan: NVENC (NVIDIA) -> AMF (AMD) -> QSV (Intel) -> libx264 (CPU)."""
    enc = available_encoders()
    for cand in ("h264_nvenc", "h264_amf", "h264_qsv", "libx264"):
        if cand in enc:
            return cand
    return "libx264"  # asumsi aman kalau daftar encoder tidak terbaca


def get_duration(path: str | Path) -> float:
    return media_info(path)["duration"]
