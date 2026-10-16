"""Tahap 5 — AI Membuat Teks Narasi Review dari Potongan Klip (Multimodal).

Tiap klip diunggah ke Google AI Studio File API (client.files.upload),
Gemini menonton langsung klipnya, lalu menulis narasi review.
Batas kata per klip memakai rumus plan: Wmax = floor(Dclip * 2.5).
Setelah selesai, file sementara di server DIHAPUS (client.files.delete).

FALLBACK: tanpa API key / API gagal -> narasi template dari ringkasan
adegan, dipotong ke Wmax kata, supaya pipeline tetap jalan.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.logger import Logger
from ..utils.time_parser import max_words_for_clip


def _trim_words(text: str, wmax: int) -> str:
    words = text.split()
    if len(words) > wmax:
        return " ".join(words[:wmax]) + "."
    return text


def _gemini_narration(client, clip_file: str, scene: dict, wmax: int,
                      style: str, model: str) -> str:
    uploaded = client.files.upload(file=clip_file)
    try:
        prompt = (
            f"Tonton klip video ini lalu tulis narasi review / recap film "
            f"dalam Bahasa Indonesia, gaya {style}. Ceritakan apa yang terlihat "
            f"di layar (aksi, ekspresi, suasana) dan kenapa adegan ini penting. "
            f"Ringkasan adegan dari tim: {scene.get('scene_summary', '')}. "
            f"MAKSIMAL {wmax} kata, kalimat lengkap, tanpa spoiler di luar klip ini."
        )
        resp = client.models.generate_content(
            model=model, contents=[prompt, uploaded])
        return (resp.text or "").strip()
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def generate_narration(clips: list[dict], work_dir: str | Path,
                       api_key: str = "", model: str = "gemini-2.5-flash",
                       style: str = "Sinematik", words_per_second: float = 2.5,
                       logger: Logger | None = None) -> list[dict]:
    log = logger or Logger()
    client = None
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
        except Exception as e:
            log.warn(f"google-genai tidak bisa dipakai ({e}). Pakai narasi cadangan.")
    out: list[dict] = []
    for clip in clips:
        wmax = max_words_for_clip(clip.get("duration", 10), words_per_second)
        text = ""
        if client:
            try:
                text = _gemini_narration(client, clip["file"], clip, wmax, style, model)
            except Exception as e:
                log.warn(f"Narasi AI klip {clip['clip_id']} gagal ({e}). Pakai cadangan.")
        if not text:
            text = (f"Di adegan ini, {clip.get('scene_summary', 'cerita terus berjalan')}. "
                    f"Momen ini penting untuk alur film.")
        text = _trim_words(text, wmax)
        item = dict(clip)
        item["narration"] = text
        item["wmax"] = wmax
        item["word_count"] = len(text.split())
        out.append(item)
        log.log(f"Narasi klip {clip['clip_id']}: {item['word_count']}/{wmax} kata")
    out_path = Path(work_dir) / "narration_script.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
