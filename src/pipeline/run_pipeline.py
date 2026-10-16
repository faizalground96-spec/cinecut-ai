"""Orkestrator 8 tahap: Input -> Transkrip -> Pilih Klip -> Potong ->
Narasi -> TTS -> Komposisi -> Render + Metadata."""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..utils.logger import Logger
from . import step1_ingest, step2_subtitle, step3_ai_selector, step4_cutter
from . import step5_ai_narrator, step6_tts, step7_composer, step8_exporter


def run_pipeline(cfg: Config, input_path: str, external_srt: str | None = None,
                 logger: Logger | None = None) -> dict:
    log = logger or Logger()
    work = Path(cfg.work_dir)
    (work / "clips").mkdir(parents=True, exist_ok=True)
    (work / "audio").mkdir(parents=True, exist_ok=True)
    (work / "subtitles").mkdir(parents=True, exist_ok=True)
    (work / "output").mkdir(parents=True, exist_ok=True)

    log.log("=== Tahap 1: Input Film ===")
    info = step1_ingest.ingest(input_path, log)
    log.log("=== Tahap 2: Ambil Transkrip ===")
    transcript = step2_subtitle.extract_transcript(
        info["path"], work, external_srt=external_srt, api_key=cfg.api_key, logger=log)
    log.log("=== Tahap 3: AI Pilih Adegan ===")
    clips = step3_ai_selector.select_scenes(
        transcript, work, target_minutes=cfg.target_minutes,
        api_key=cfg.api_key, model=cfg.model, logger=log)
    log.log("=== Tahap 4: Potong Klip ===")
    cut = step4_cutter.cut_clips(info["path"], clips, work,
                                 keep_ambient_db=cfg.keep_ambient_db, logger=log)
    log.log("=== Tahap 5: AI Buat Narasi ===")
    narr = step5_ai_narrator.generate_narration(
        cut, work, api_key=cfg.api_key, model=cfg.model, style=cfg.style,
        words_per_second=cfg.words_per_second, logger=log)
    log.log("=== Tahap 6: TTS + Subtitel ===")
    voiced = step6_tts.synthesize(
        narr, work, api_key=cfg.api_key, tts_model=cfg.tts_model,
        edge_voice=cfg.edge_tts_voice, words_per_second=cfg.words_per_second, logger=log)
    log.log("=== Tahap 7: Komposisi ===")
    composed = step7_composer.compose(
        voiced, work, aspect=cfg.aspect, flip=cfg.flip_enabled,
        zoom=cfg.zoom_enabled, logger=log)
    log.log("=== Tahap 8: Render + Paket Upload ===")
    final = step8_exporter.render_final(
        composed, work / "output" / "CineCut_Hasil.mp4", aspect=cfg.aspect, logger=log)
    meta = step8_exporter.make_upload_metadata(
        voiced, work / "output" / "upload_metadata.txt",
        api_key=cfg.api_key, model=cfg.model, logger=log)
    log.log("SELESAI! Video final dan paket upload sudah jadi.")
    return {"video": str(final), "metadata": str(meta), "clips": len(voiced)}
