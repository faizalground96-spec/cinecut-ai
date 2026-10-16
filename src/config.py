"""Pengaturan CineCut AI.

API key TIDAK PERNAH ditulis di kode / di GitHub.
Urutan baca kunci: argumen CLI / kolom GUI -> variabel env GEMINI_API_KEY
-> file .env di root proyek -> file .env di folder kerja.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv_file(path: Path) -> dict:
    values: dict = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


@dataclass
class Config:
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    tts_model: str = "gemini-2.5-flash-preview-tts"
    edge_tts_voice: str = "id-ID-ArdiNeural"
    target_minutes: float = 10.0
    aspect: str = "16:9"  # "16:9" atau "9:16"
    style: str = "Sinematik"  # Santai / Sinematik / Komedi / Tegang
    flip_enabled: bool = False  # Efek cermin, opsional. BUKAN jaminan lolos Content ID.
    zoom_enabled: bool = True  # Zoom / crop ringan 1.05x-1.10x, opsional.
    keep_ambient_db: float = -25.0  # Volume suara asli film sebagai ambiens.
    work_dir: Path = field(default_factory=lambda: Path("workspace"))
    # Kecepatan bicara narator rata-rata (kata per detik) — sesuai plan.
    words_per_second: float = 2.5

    @classmethod
    def load(cls, api_key: str = "", work_dir: str = "workspace") -> "Config":
        cfg = cls(work_dir=Path(work_dir))
        # .env di root proyek (satu level di atas src/) + .env di work_dir
        for env_path in (Path(__file__).resolve().parent.parent / ".env",
                         Path(work_dir) / ".env"):
            for k, v in _load_dotenv_file(env_path).items():
                os.environ.setdefault(k, v)
        cfg.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        ).strip()
        cfg.model = os.environ.get("GEMINI_MODEL", cfg.model)
        cfg.tts_model = os.environ.get("GEMINI_TTS_MODEL", cfg.tts_model)
        cfg.edge_tts_voice = os.environ.get("EDGE_TTS_VOICE", cfg.edge_tts_voice)
        return cfg
