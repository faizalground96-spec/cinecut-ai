"""Pemutar pratinjau sederhana: tombol buka video hasil di pemutar sistem."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_video(path: str | Path) -> None:
    """Buka video hasil dengan aplikasi bawaan Windows / sistem."""
    p = str(path)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606 - path berasal dari hasil pipeline sendiri
    elif sys.platform == "darwin":
        subprocess.run(["open", p], check=False)
    else:
        subprocess.run(["xdg-open", p], check=False)


def preview_widget_info(video_path: str | Path) -> str:
    p = Path(video_path)
    if p.exists():
        return f"Hasil: {p.name} ({p.stat().st_size / 1_000_000:.1f} MB)"
    return "Belum ada video hasil."
