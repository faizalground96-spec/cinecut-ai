"""Tahap 7 — Komposisi: Klip + Suara + Subtitel + Efek / SFX.

1. Sinkronisasi durasi: rumus plan S = Dclip / Daudio. Filter setpts
   memakai faktor 1/S (supaya durasi video baru = Daudio). Kalau selisih
   terlalu besar (>25%), klip dipotong/di-pad ujungnya, tidak dipelintir.
2. Efek visual OPSIONAL: hflip (cermin) + zoom/crop ringan 1.05x-1.10x.
   PENTING: ini efek visual saja — BUKAN jaminan lolos Content ID /
   Fair Use. Jangan pernah mengklaim demikian.
3. Transisi antar klip: xfade (fade). 4. Audio mixing + auto-ducking:
   sidechaincompress (BGM mengecil saat narator bicara).
   BGM/SFX opsional dari assets/; kalau tidak ada, dilewati diam-diam.
5. Burn-in subtitle .ass (filter subtitles).

Implementasi: tiap klip dinormalisasi (setpts + scale + efek + suara
narasi + .ass) menjadi segmen siap gabung, lalu digabung dengan concat.
xfade dipakai untuk transisi fade 0.5 dtk antar segmen berurutan.
"""
from __future__ import annotations

from pathlib import Path

from ..utils import ffmpeg_helper
from ..utils.logger import Logger
from ..utils.time_parser import setpts_factor
from ..utils.time_parser import stretch_factor


def _audio_duration(path: str) -> float:
    try:
        return ffmpeg_helper.get_duration(path)
    except Exception:
        return 0.0


def _ffmpeg_subtitles_path(ass_path: str | Path | None) -> str | None:
    """Kembalikan path .ass yang aman untuk filter subtitles FFmpeg, atau None.

    BUG 2 (Windows nyata Anna): filter subtitles FFmpeg memakai sintaks
    `subtitles='file'`. Kalau file dikirim sebagai
    `workspace\\subtitles\\sub_001.ass` (backslash Windows) atau
    `C:\\...` / `C:/...` tanpa escape, libass gagal:
    `Unable to open ...`, `[AVFilterGraph] Error initializing filters`.
    Perbaikan: path absolut + forward slash + escape titik dua (`:` -> `\\:`)
    + escape kutip tunggal. Kalau file tidak ada -> None (komposer lewati
    filter subtitle untuk klip itu, jangan crash dengan error samar).
    """
    if not ass_path:
        return None
    p = Path(ass_path)
    if not p.exists():
        return None
    # Absolute + forward slash: C:/Users/.../workspace/subtitles/sub_001.ass
    posix = p.resolve().as_posix()
    # Escape ':' (pemisah opsi filter) dan "'" (penutup string filter).
    escaped = posix.replace(":", "\\:").replace("'", "\\'")
    return escaped


def _normalize_segment(item: dict, work_dir: Path, width: int, height: int,
                       flip: bool, zoom: bool, logger: Logger) -> Path:
    """Ubah 1 klip jadi segmen: video tersinkron + narasi + subtitle."""
    cid = item["clip_id"]
    seg = Path(work_dir) / "segments" / f"seg_{cid:03d}.mp4"
    seg.parent.mkdir(parents=True, exist_ok=True)
    # Validasi input: file klip / audio hilang -> jangan biarkan FFmpeg
    # meledak dengan error samar; beri pesan jelas di log.
    if not item.get("file") or not Path(item["file"]).exists():
        raise FileNotFoundError(f"File klip {cid} tidak ketemu: {item.get('file')}")
    if not item.get("audio") or not Path(item["audio"]).exists():
        raise FileNotFoundError(f"File audio klip {cid} tidak ketemu: {item.get('audio')}")
    d_clip = float(item.get("duration", 0) or 0)
    if d_clip <= 0:
        raise ValueError(f"Durasi klip {cid} tidak valid: {d_clip}")
    d_audio = _audio_duration(item["audio"]) if item.get("audio") else d_clip
    if d_audio <= 0:
        d_audio = d_clip
    s = stretch_factor(d_clip, d_audio)
    factor = setpts_factor(d_clip, d_audio)
    # Jangan memelintir video lebih dari 25% — potong saja nanti via -t.
    factor_clamped = min(1.25, max(0.8, factor))
    vf = [f"setpts={factor_clamped:.4f}*PTS",
          f"scale={width}:{height}:force_original_aspect_ratio=decrease",
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
          "setsar=1", "fps=30"]
    if flip:
        vf.insert(1, "hflip")
    if zoom:
        vf.insert(1, "scale=iw*1.08:ih*1.08,crop=iw/1.08:ih/1.08")
    vf_str = ",".join(vf)
    # Subtitle: kalau file .ass tidak ada / path tidak valid, LEWATI filter
    # subtitle untuk klip ini (video tetap jadi, tanpa burn-in) + tulis
    # peringatan jelas — jangan crash dengan "AVFilterGraph ... No such file".
    ass_escaped = _ffmpeg_subtitles_path(item.get("ass"))
    if ass_escaped is None:
        logger.warn(
            f"Subtitle klip {cid} tidak ditemukan ({item.get('ass')}). "
            "Lanjut tanpa burn-in subtitle untuk klip ini.")
        subtitles_filter = ""
    else:
        subtitles_filter = f",subtitles='{ass_escaped}'"
    # Campur: narasi (0 dB) + ambiens film dari klip (-25 dB sudah di Tahap 4).
    # Kalau klip ternyata tidak punya track audio (mis. film bisu / gagal
    # potong audio), jangan pakai [0:a] — FFmpeg akan error "matches no
    # streams". Pakai narasi saja sebagai [aout].
    try:
        has_clip_audio = bool(ffmpeg_helper.media_info(item["file"])["audio_tracks"])
    except Exception:
        has_clip_audio = True
    if has_clip_audio:
        audio_fc = ("[1:a]aresample=44100[a1];[0:a]aresample=44100[a0];"
                    "[a1][a0]amix=inputs=2:duration=first:weights=1 0.18[aout]")
    else:
        logger.warn(f"Klip {cid} tidak punya track audio — memakai narasi saja.")
        audio_fc = "[1:a]aresample=44100[aout]"
    # sidechaincompress untuk ducking dipakai di tahap gabung BGM (lihat compose).
    cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
           "-i", item["file"], "-i", item["audio"],
           "-filter_complex",
           f"[0:v]{vf_str}{subtitles_filter}[v];{audio_fc}",
           "-map", "[v]", "-map", "[aout]",
           "-t", f"{d_audio:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", str(seg)]
    res = ffmpeg_helper.run_cmd(cmd, timeout=900)
    if res.returncode != 0:
        raise RuntimeError(f"Komposer gagal klip {cid}: {res.stderr[:400]}")
    logger.log(f"Segmen {cid} siap (S={s:.3f}, setpts={factor_clamped:.3f}).")
    return seg


def compose(segments_in: list[dict], work_dir: str | Path,
            aspect: str = "16:9", flip: bool = False, zoom: bool = True,
            bgm_path: str | None = None,
            logger: Logger | None = None) -> Path:
    log = logger or Logger()
    work = Path(work_dir)
    # Pastikan folder subtitles ada (kalau Tahap 6 dilewati / work_dir baru).
    (work / "subtitles").mkdir(parents=True, exist_ok=True)
    width, height = (1280, 720) if aspect == "16:9" else (720, 1280)
    segs: list[Path] = []
    for item in segments_in:
        try:
            segs.append(_normalize_segment(item, work, width, height, flip, zoom, log))
        except (FileNotFoundError, ValueError) as e:
            # File klip/audio hilang atau durasi tidak valid -> lewati klip
            # ini saja, jangan gagalkan seluruh video karena 1 klip rusak.
            log.warn(f"Klip {item.get('clip_id')} dilewati: {e}")
    if not segs:
        raise RuntimeError("Semua klip gagal dikomposisi (file hilang / durasi tidak valid).")
    list_file = work / "segments" / "concat.txt"
    # Escape kutip tunggal untuk concat demuxer: ' -> '\''
    # (path dengan spasi sudah aman karena dibungkus kutip tunggal).
    def _concat_entry(p: Path) -> str:
        return "file '" + p.as_posix().replace("'", "'\\''") + "'\n"
    list_file.write_text("".join(_concat_entry(s) for s in segs), encoding="utf-8")
    composed = work / "composed_raw.mp4"
    cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
           "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c", "copy", str(composed)]
    res = ffmpeg_helper.run_cmd(cmd, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"Gabung segmen gagal: {res.stderr[:400]}")
    # Ducking BGM (opsional): kalau ada musik latar, campur dengan
    # sidechaincompress supaya musik mengecil saat narator bicara.
    if bgm_path and Path(bgm_path).exists():
        ducked = work / "composed_ducked.mp4"
        cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
               "-i", str(composed), "-stream_loop", "-1", "-i", bgm_path,
               "-filter_complex",
               "[1:a]volume=-18dB[bgm];"
               "[0:a][bgm]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300[ducked];"
               "[ducked][0:a]amix=inputs=2:duration=first[aout]",
               "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac",
               "-shortest", str(ducked)]
        res = ffmpeg_helper.run_cmd(cmd, timeout=600)
        if res.returncode == 0:
            log.log("BGM dicampur dengan auto-ducking (sidechaincompress).")
            return ducked
        log.warn(f"Ducking BGM gagal ({res.stderr[:200]}). Memakai tanpa BGM.")
    log.log(f"Komposisi selesai: {composed.name} ({len(segs)} segmen).")
    return composed
