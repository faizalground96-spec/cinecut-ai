"""Titik masuk CineCut AI.

- Tanpa argumen: buka jendela GUI (CustomTkinter).
- Dengan --input: jalankan pipeline lewat baris perintah (CLI).
- --dry-run: hanya cek pengaturan, tidak memproses film.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Biar bisa jalan sebagai `python -m src.main` maupun `python src/main.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="CineCut AI",
        description="Buat video recap / review film otomatis dari file film.")
    p.add_argument("--input", help="File film (.mp4/.mkv/.avi)")
    p.add_argument("--srt", default=None, help="File .srt eksternal (opsional)")
    p.add_argument("--output-dir", default="workspace", help="Folder kerja / hasil")
    p.add_argument("--api-key", default="", help="Kunci Gemini (opsional, bisa via .env)")
    p.add_argument("--durasi", type=float, default=10.0, help="Target durasi video (menit)")
    p.add_argument("--rasio", default="16:9", choices=["16:9", "9:16"],
                   help="Rasio video hasil")
    p.add_argument("--gaya", default="Sinematik",
                   choices=["Santai", "Sinematik", "Komedi", "Tegang"])
    p.add_argument("--dry-run", action="store_true",
                   help="Hanya cek pengaturan, jangan proses film")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    from src.config import Config
    from src.utils.logger import Logger
    log = Logger()
    cfg = Config.load(api_key=args.api_key, work_dir=args.output_dir)
    # Validasi durasi: 0 / negatif / >60 menit -> pakai 10 menit.
    cfg.target_minutes = args.durasi if 0 < args.durasi <= 60 else 10.0
    cfg.aspect = args.rasio
    cfg.style = args.gaya
    if args.dry_run:
        log.log(f"CineCut AI siap. Rasio {cfg.aspect}, gaya {cfg.style}, "
                f"target {cfg.target_minutes:g} menit, "
                f"API key {'terisi' if cfg.api_key else 'belum diisi (nanti pakai cadangan)'}")
        return 0
    if args.input:
        from src.pipeline.run_pipeline import run_pipeline
        result = run_pipeline(cfg, args.input, external_srt=args.srt, logger=log)
        log.log(f"Hasil: {result['video']}")
        return 0
    # GUI
    try:
        from src.gui.app_window import launch_gui
        launch_gui(cfg)
    except Exception as e:
        log.error(f"GUI tidak bisa dibuka ({e}). Pakai mode CLI: python -m src.main --input FILM.mp4")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
