"""Tahap 2 — Ambil Transkrip / Subtitle.

Prioritas sesuai plan:
  1. Subtitle yang tertanam di file (embedded) -> diekstrak FFmpeg jadi .srt
  2. File .srt eksternal yang dipilih pengguna
  3. Fallback: Faster-Whisper (lokal) atau Gemini STT dari audio 16kHz mono

Output: transcript_clean.json -> daftar {id, start_time, end_time, text}
dengan start_time / end_time format "HH:MM:SS.mmm" + start_seconds/end_seconds.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..utils import ffmpeg_helper
from ..utils.logger import Logger
from ..utils.time_parser import seconds_to_clock, srt_to_seconds

_SRT_BLOCK = re.compile(
    r"(\d+)\s*\n(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL)


def parse_srt(srt_text: str) -> list[dict]:
    """Ubah isi .srt menjadi daftar dialog bersih (tag HTML / ASS dibuang)."""
    out: list[dict] = []
    for m in _SRT_BLOCK.finditer(srt_text.replace("\r\n", "\n")):
        _num, start, end, body = m.groups()
        text = re.sub(r"<[^>]+>", "", body)
        text = re.sub(r"\{[^}]*\}", "", text).strip().replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        out.append({
            "id": len(out) + 1,
            "start_time": seconds_to_clock(srt_to_seconds(start)),
            "end_time": seconds_to_clock(srt_to_seconds(end)),
            "start_seconds": round(srt_to_seconds(start), 3),
            "end_seconds": round(srt_to_seconds(end), 3),
            "text": text,
        })
    return out


def _extract_embedded(video_path: str, out_srt: Path, logger: Logger) -> bool:
    cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
           "-i", video_path, "-map", "0:s:0", str(out_srt)]
    res = ffmpeg_helper.run_cmd(cmd, timeout=300)
    if res.returncode == 0 and out_srt.exists() and out_srt.stat().st_size > 0:
        logger.log("Subtitle tertanam berhasil diekstrak.")
        return True
    logger.warn("Tidak ada subtitle tertanam yang bisa diekstrak.")
    return False


def _transcribe_with_whisper(video_path: str, out_dir: Path, logger: Logger) -> list[dict]:
    """Fallback lokal: ekstrak audio 16kHz mono -> Faster-Whisper."""
    # Kalau film tidak punya track audio sama sekali, transkripsi mustahil
    # (FFmpeg akan gagal "Output file does not contain any stream").
    # Beri pesan jelas, jangan biarkan error samar itu sampai ke pengguna.
    try:
        has_audio = bool(ffmpeg_helper.media_info(video_path)["audio_tracks"])
    except Exception:
        has_audio = True
    if not has_audio:
        raise RuntimeError(
            "Film ini tidak punya track audio, jadi suaranya tidak bisa "
            "ditranskripsi. Sediakan file subtitle .srt eksternal.")
    wav = out_dir / "audio_16k.wav"
    cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
           "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", str(wav)]
    res = ffmpeg_helper.run_cmd(cmd, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"Gagal ekstrak audio untuk transkripsi: {res.stderr[:300]}")
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "Faster-Whisper belum terpasang (pip install faster-whisper) "
            "dan tidak ada subtitle. Pasang subtitle .srt atau install Faster-Whisper.") from e
    logger.log("Menjalankan Faster-Whisper (lokal)... ini bisa agak lama.")
    try:
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(wav), language=None)
    except Exception as e:
        raise RuntimeError(
            "Transkripsi Faster-Whisper gagal (model belum terunduh / tidak ada "
            f"internet / memori tidak cukup): {e}. Sediakan file subtitle .srt "
            "eksternal supaya tidak perlu transkripsi.") from e
    out = []
    for seg in segments:
        out.append({"id": len(out) + 1,
                    "start_time": seconds_to_clock(seg.start),
                    "end_time": seconds_to_clock(seg.end),
                    "start_seconds": round(seg.start, 3),
                    "end_seconds": round(seg.end, 3),
                    "text": seg.text.strip()})
    return out


def extract_transcript(video_path: str, work_dir: str | Path,
                       external_srt: str | None = None,
                       api_key: str = "",
                       logger: Logger | None = None) -> list[dict]:
    log = logger or Logger()
    work = Path(work_dir)
    (work / "subtitles").mkdir(parents=True, exist_ok=True)
    raw_srt = work / "subtitles" / "raw_subtitles.srt"

    # Jalur 2 — .srt eksternal (didahulukan kalau pengguna menyediakannya)
    if external_srt:
        p = Path(external_srt)
        if not p.exists():
            raise FileNotFoundError(f"File .srt tidak ketemu: {p}")
        transcript = parse_srt(p.read_text(encoding="utf-8", errors="replace"))
        log.log(f"Memakai subtitle eksternal: {p.name} ({len(transcript)} dialog)")
    # Jalur 1 — embedded
    elif _extract_embedded(video_path, raw_srt, log):
        transcript = parse_srt(raw_srt.read_text(encoding="utf-8", errors="replace"))
        log.log(f"Subtitle tertanam: {len(transcript)} dialog")
    # Jalur 3 — fallback STT
    else:
        log.log("Tidak ada subtitle — memakai transkripsi suara (Faster-Whisper).")
        transcript = _transcribe_with_whisper(video_path, work, log)
        log.log(f"Transkripsi selesai: {len(transcript)} segmen")

    if not transcript:
        raise RuntimeError("Transkrip kosong. Coba sediakan file .srt eksternal.")
    out_json = work / "subtitles" / "transcript_clean.json"
    out_json.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    return transcript
