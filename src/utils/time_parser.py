"""Konversi format waktu: SRT / HH:MM:SS.mmm <-> detik (float).

Dipakai di semua tahap: subtitle, pemotong klip, TTS, komposer.
"""
from __future__ import annotations

import math
import re

_SRT_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def srt_to_seconds(text: str) -> float:
    """'00:45:12,000' atau '00:45:12.000' -> 2712.0. Juga terima '75.5' / '75'."""
    text = (text or "").strip()
    m = _SRT_RE.match(text)
    if m:
        h, mi, s, ms = (int(x) for x in m.groups())
        return h * 3600 + mi * 60 + s + ms / 1000.0
    return float(text)


def seconds_to_srt(seconds: float) -> str:
    """2712.0 -> '00:45:12,000' (format SRT)."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    mi, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def seconds_to_clock(seconds: float) -> str:
    """2712.5 -> '00:45:12.500' (format FFmpeg -ss/-to)."""
    return seconds_to_srt(seconds).replace(",", ".")


def seconds_to_ass(seconds: float) -> str:
    """2712.5 -> '0:45:12.50' (format .ass, centiseconds)."""
    total_cs = max(0, int(round(float(seconds) * 100)))
    h, rem = divmod(total_cs, 360_000)
    mi, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{mi:02d}:{s:02d}.{cs:02d}"


def max_words_for_clip(clip_duration: float, words_per_second: float = 2.5) -> int:
    """Rumus plan Tahap 5: Wmax = floor(Dclip * 2.5)."""
    return max(1, math.floor(float(clip_duration) * float(words_per_second)))


def stretch_factor(clip_duration: float, audio_duration: float) -> float:
    """Rumus plan Tahap 7: S = Dclip / Daudio.

    Faktor setpts yang dipakai FFmpeg adalah 1/S (supaya durasi video
    baru = Dclip * (1/S) = Daudio). Fungsi ini mengembalikan S sesuai plan.
    """
    if audio_duration <= 0:
        return 1.0
    return float(clip_duration) / float(audio_duration)


def setpts_factor(clip_duration: float, audio_duration: float) -> float:
    """Faktor pengali PTS untuk filter setpts: Daudio / Dclip (= 1/S)."""
    s = stretch_factor(clip_duration, audio_duration)
    if s <= 0:
        return 1.0
    return 1.0 / s
