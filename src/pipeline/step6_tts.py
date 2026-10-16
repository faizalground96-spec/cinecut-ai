"""Tahap 6 — Generate Text-to-Voice (TTS) + Word Timestamps.

Jalur utama: Gemini TTS (gemini-3.8-flash; model 2.5-preview-tts sudah mati).
Kalau Gemini TTS gagal (mis. 404 / model tidak dukung AUDIO) -> Edge-TTS.
Jalur cadangan: edge-tts (id-ID-ArdiNeural / id-ID-GadisNeural) — sekaligus
menghasilkan WordBoundary (waktu tiap kata) untuk subtitle .ass.
Jalur terakhir: file suara hening sepanjang estimasi (kata / 2.5) + .ass
per kalimat, supaya pipeline tetap selesai dan pengguna tahu TTS gagal.

Output per klip: voice_XXX.wav + subtitle .ass.
Format .ass: font Montserrat ExtraBold, outline hitam, pop-up per kata/frasa.
"""
from __future__ import annotations

import asyncio
import base64
import json
import struct
import wave
from pathlib import Path

from ..config import DEFAULT_TTS_MODEL, is_not_found_error, resolve_model
from ..utils.logger import Logger
from ..utils.time_parser import seconds_to_ass

ASS_HEADER = """[Script Info]
Title: CineCut AI Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narasi,Montserrat ExtraBold,26,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2.5,0,2,20,20,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(path: Path, word_times: list[tuple[float, float, str]]) -> None:
    """word_times: [(start, end, kata/frasa)] -> file .ass."""
    # BUG 2: pastikan direktori tujuan ada sebelum nulis, supaya Tahap 7
    # tidak gagal "Unable to open ... sub_XXX.ass" karena folder belum dibuat.
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [ASS_HEADER]
    for start, end, word in word_times:
        safe = word.replace("{", "").replace("}", "").strip()
        if not safe:
            continue
        lines.append(
            f"Dialogue: 0,{seconds_to_ass(start)},{seconds_to_ass(end)},"
            f"Narasi,,0,0,0,,{{\\fad(80,80)}}{safe}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_silence(path: Path, seconds: float, rate: int = 24000) -> None:
    n = max(1, int(seconds * rate))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<h", 0) * n)


def _gemini_tts_once(client, text: str, out_wav: Path, model: str) -> bool:
    """Satu percobaan Gemini TTS. Kembalikan True kalau berhasil."""
    try:
        from google.genai import types
        resp = client.models.generate_content(
            model=model, contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Charon")))))
        for cand in getattr(resp, "candidates", []) or []:
            for part in getattr(cand, "content", None).parts or []:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if data:
                    raw = base64.b64decode(data) if isinstance(data, str) else data
                    # Gemini TTS umumnya PCM 24kHz mono 16-bit
                    with wave.open(str(out_wav), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw)
                    return True
    except Exception as e:
        # Biarkan 404 NOT_FOUND naik supaya wrapper bisa coba model default.
        if is_not_found_error(e):
            raise
        return False
    return False


def _gemini_tts(client, text: str, out_wav: Path, model: str) -> bool:
    """Kembalikan True kalau berhasil. Model 2.5 lama -> coba 3.8-flash sekali.

    Kalau model 3.8 juga gagal (mis. tidak dukung AUDIO / 404), kembalikan
    False supaya pemanggil jatuh ke Edge-TTS, bukan crash.
    """
    # Jangan normalkan dulu: kalau pemanggil masih mengirim model lama
    # (mis. 2.5 dari .env lama), percobaan pertama akan 404, lalu kita
    # coba sekali lagi dengan model default 3.8-flash.
    requested = (model or "").strip() or DEFAULT_TTS_MODEL
    try:
        if _gemini_tts_once(client, text, out_wav, requested):
            return True
    except Exception as e:
        if not is_not_found_error(e):
            return False
        # 404 -> coba sekali lagi dengan default
        if requested != DEFAULT_TTS_MODEL:
            try:
                return _gemini_tts_once(client, text, out_wav, DEFAULT_TTS_MODEL)
            except Exception:
                return False
        return False
    return False


def _edge_tts(text: str, out_wav: Path, voice: str) -> list[tuple[float, float, str]]:
    """Jalankan edge-tts, kembalikan word boundaries [(start, end, kata)]."""
    import edge_tts
    boundaries: list[tuple[float, float, str]] = []

    async def _run():
        comm = edge_tts.Communicate(text, voice)
        with open(out_wav, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append((chunk["offset"] / 10_000_000,
                                       (chunk["offset"] + chunk["duration"]) / 10_000_000,
                                       chunk["text"]))
    asyncio.run(_run())
    return boundaries


def synthesize(narrations: list[dict], work_dir: str | Path,
               api_key: str = "", tts_model: str = DEFAULT_TTS_MODEL,
               edge_voice: str = "id-ID-ArdiNeural",
               words_per_second: float = 2.5,
               logger: Logger | None = None) -> list[dict]:
    log = logger or Logger()
    audio_dir = Path(work_dir) / "audio"
    sub_dir = Path(work_dir) / "subtitles"
    audio_dir.mkdir(parents=True, exist_ok=True)
    sub_dir.mkdir(parents=True, exist_ok=True)
    client = None
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
        except Exception:
            client = None
    out: list[dict] = []
    for item in narrations:
        cid = item["clip_id"]
        wav = audio_dir / f"voice_{cid:03d}.wav"
        ass = sub_dir / f"sub_{cid:03d}.ass"
        text = item["narration"]
        word_times: list[tuple[float, float, str]] = []
        done = False
        if client:
            done = _gemini_tts(client, text, wav, tts_model)
            if done:
                log.log(f"TTS Gemini klip {cid} selesai.")
        if not done:
            try:
                word_times = _edge_tts(text, wav, edge_voice)
                done = True
                log.log(f"TTS Edge ({edge_voice}) klip {cid} selesai.")
            except Exception as e:
                log.warn(f"TTS Edge klip {cid} gagal ({e}). Memakai suara hening cadangan.")
        if not done or not wav.exists():
            est = max(1.0, len(text.split()) / words_per_second)
            _write_silence(wav, est)
        if not word_times:
            # Perkiraan per kata merata (untuk .ass) bila tanpa WordBoundary.
            est = max(1.0, len(text.split()) / words_per_second)
            per = est / max(1, len(text.split()))
            word_times = [(i * per, (i + 1) * per, w)
                          for i, w in enumerate(text.split())]
        write_ass(ass, word_times)
        new = dict(item)
        new["audio"] = str(wav)
        new["ass"] = str(ass)
        out.append(new)
    (Path(work_dir) / "tts_manifest.json").write_text(
        json.dumps([{"clip_id": o["clip_id"], "audio": o["audio"], "ass": o["ass"]}
                    for o in out], ensure_ascii=False, indent=2), encoding="utf-8")
    return out
