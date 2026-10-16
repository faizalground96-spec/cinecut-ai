"""Bungkus CineCut AI jadi .exe Windows (PyInstaller).

Dipakai di PC Windows dan di GitHub Actions (windows-latest).
Jalankan dari root proyek:  python scripts/build_exe.py
Hasil: dist/CineCutAI/CineCutAI.exe (+ folder pendukung) dan,
kalau Inno Setup tersedia, installer CineCutAI_Setup.exe.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    icon = ROOT / "assets" / "icons" / "app.ico"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
           "--windowed", "--name", "CineCutAI",
           "--add-data", f"assets{os.pathsep}assets",
           "--add-data", f"bin{os.pathsep}bin",
           str(ROOT / "src" / "main.py")]
    if icon.exists():
        cmd += ["--icon", str(icon)]
    print("Menjalankan:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        return res.returncode
    exe = ROOT / "dist" / "CineCutAI" / "CineCutAI.exe"
    print(f"Selesai. EXE: {exe} (ada: {exe.exists()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
