"""Tahap 3 — AI Analisis & Pilih Bagian Terbaik (Scene Selection).

Mengirim transkrip ke Gemini (gemini-2.5-flash) dengan Structured Output
(response_schema JSON ketat) sesuai plan Section 3. Hasilnya daftar klip:
{clip_id, phase, start_time, end_time, scene_summary, dramatic_score, suggested_sfx}

FALLBACK: kalau tidak ada API key / API gagal, dipakai pembagian adegan
merata (heuristic) supaya pipeline tetap jalan dan pengguna tetap dapat
hasil — dengan catatan jelas di log bahwa ini BUKAN hasil AI.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.logger import Logger
from ..utils.time_parser import seconds_to_clock, srt_to_seconds

PHASES = ["HOOK", "PENGENALAN", "KONFLIK", "KLIMAKS", "TWIST_ENDING"]
CLIP_MIN, CLIP_MAX = 8.0, 30.0


def _fallback_clips(transcript: list[dict], target_minutes: float) -> list[dict]:
    """Bagi cerita jadi klip merata di sepanjang film (tanpa AI)."""
    if not transcript:
        return []
    total = transcript[-1]["end_seconds"]
    n = max(5, min(20, int(target_minutes * 1.5)))
    clips: list[dict] = []
    step = total / n
    for i in range(n):
        start = i * step
        end = min(total, start + max(CLIP_MIN, min(CLIP_MAX, step * 0.6)))
        nearby = [d["text"] for d in transcript
                  if d["start_seconds"] >= start and d["start_seconds"] < end][:2]
        clips.append({
            "clip_id": i + 1,
            "phase": PHASES[min(i * len(PHASES) // n, len(PHASES) - 1)],
            "start_time": seconds_to_clock(start),
            "end_time": seconds_to_clock(end),
            "scene_summary": " ".join(nearby)[:200] or "Adegan dari film",
            "dramatic_score": 7.0,
            "suggested_sfx": "whoosh",
        })
    return clips


def _gemini_clips(transcript: list[dict], target_minutes: float, api_key: str,
                  model: str, logger: Logger) -> list[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    text = "\n".join(
        f"[{d['start_time']} - {d['end_time']}] {d['text']}" for d in transcript)
    prompt = (
        "Analisis alur cerita film ini dari transkrip berikut. "
        f"Pilih 15-25 adegan kunci yang membangun struktur cerita utuh "
        "(Hook/Pembuka, Pengenalan Konflik, Klimaks, dan Twist/Ending) "
        f"untuk video review berdurasi {target_minutes:g} menit. "
        "Tiap klip berdurasi 8-30 detik, jangan tumpang tindih, urut waktu. "
        "Jangan membocorkan twist akhir di ringkasan kalau tidak perlu.\n\n"
        f"TRANSKRIP:\n{text[:90000]}"
    )
    schema = types.Schema(
        type=types.Type.ARRAY,
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "clip_id": types.Schema(type=types.Type.INTEGER),
                "phase": types.Schema(type=types.Type.STRING),
                "start_time": types.Schema(type=types.Type.STRING),
                "end_time": types.Schema(type=types.Type.STRING),
                "scene_summary": types.Schema(type=types.Type.STRING),
                "dramatic_score": types.Schema(type=types.Type.NUMBER),
                "suggested_sfx": types.Schema(type=types.Type.STRING),
            },
            required=["clip_id", "phase", "start_time", "end_time",
                      "scene_summary", "dramatic_score", "suggested_sfx"],
        ),
    )
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema),
    )
    raw = resp.text or "[]"
    clips = json.loads(raw)
    # Validasi + rapikan
    clean: list[dict] = []
    for i, c in enumerate(clips):
        try:
            s, e = srt_to_seconds(c["start_time"]), srt_to_seconds(c["end_time"])
        except Exception:
            continue
        if e - s < 3 or e - s > 60:
            continue
        clean.append({
            "clip_id": i + 1,
            "phase": str(c.get("phase", "KONFLIK")).upper()[:30],
            "start_time": seconds_to_clock(s),
            "end_time": seconds_to_clock(e),
            "scene_summary": str(c.get("scene_summary", ""))[:300],
            "dramatic_score": float(c.get("dramatic_score", 7.0)),
            "suggested_sfx": str(c.get("suggested_sfx", "whoosh"))[:40],
        })
    if not clean:
        raise RuntimeError("Gemini mengembalikan daftar klip kosong / tidak valid.")
    return clean


def select_scenes(transcript: list[dict], work_dir: str | Path,
                  target_minutes: float = 10.0, api_key: str = "",
                  model: str = "gemini-2.5-flash",
                  logger: Logger | None = None) -> list[dict]:
    log = logger or Logger()
    clips: list[dict] = []
    if api_key:
        try:
            log.log("Gemini menganalisis transkrip & memilih adegan terbaik...")
            clips = _gemini_clips(transcript, target_minutes, api_key, model, log)
            log.log(f"Gemini memilih {len(clips)} adegan.")
        except Exception as e:
            log.warn(f"Gemini gagal ({e}). Memakai pembagian adegan cadangan.")
    if not clips:
        clips = _fallback_clips(transcript, target_minutes)
        log.log(f"Pembagian adegan cadangan: {len(clips)} klip merata.")
    out = Path(work_dir) / "selected_clips.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clips, ensure_ascii=False, indent=2), encoding="utf-8")
    return clips
