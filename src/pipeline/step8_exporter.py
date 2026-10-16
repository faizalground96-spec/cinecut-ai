"""Tahap 8 — Render Final & Paket Siap Upload.

- Render akhir FFmpeg dengan akselerasi: h264_nvenc / h264_amf /
  h264_qsv / libx264 (dipilih otomatis lewat ffmpeg_helper).
- Rasio: 16:9 (YouTube landscape) atau 9:16 (TikTok/Shorts/Reels,
  video di tengah + latar blur).
- upload_metadata.txt: 5 judul, deskripsi SEO, hashtag, prompt thumbnail.
  Dibuat Gemini kalau ada API key, kalau tidak memakai template dari
  narasi + ringkasan adegan.
"""
from __future__ import annotations

from pathlib import Path

from ..utils import ffmpeg_helper
from ..utils.logger import Logger


# Preset per encoder: NVENC memakai p1-p7, AMF memakai speed/balanced/quality.
_ENCODER_PRESET = {"h264_nvenc": "p4", "h264_amf": "balanced",
                   "h264_qsv": "veryfast", "libx264": "veryfast"}


def render_final(composed: str | Path, out_path: str | Path,
                 aspect: str = "16:9", logger: Logger | None = None) -> Path:
    log = logger or Logger()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    preferred = ffmpeg_helper.pick_h264_encoder()
    # Coba encoder GPU dulu; kalau gagal (mis. tidak ada GPU), jatuh ke CPU.
    attempts = [preferred] + [e for e in ("libx264",) if e != preferred]
    last_err = ""
    for encoder in attempts:
        preset = _ENCODER_PRESET.get(encoder, "veryfast")
        log.log(f"Render akhir memakai encoder: {encoder} (preset {preset}, rasio {aspect})")
        if aspect == "9:16":
            vf = ("split[a][b];[a]scale=720:1280:force_original_aspect_ratio=increase,"
                  "crop=720:1280,gblur=sigma=40[bg];"
                  "[b]scale=720:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
            cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
                   "-i", str(composed), "-filter_complex", vf,
                   "-c:v", encoder, "-preset", preset, "-crf", "20",
                   "-c:a", "aac", str(out)]
        else:
            cmd = [ffmpeg_helper.find_binary("ffmpeg"), "-y", "-v", "error",
                   "-i", str(composed),
                   "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                          "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                   "-c:v", encoder, "-preset", preset, "-crf", "20",
                   "-c:a", "aac", str(out)]
        res = ffmpeg_helper.run_cmd(cmd, timeout=1800)
        if res.returncode == 0 and out.exists() and out.stat().st_size > 0:
            log.log(f"Video final: {out} ({out.stat().st_size / 1_000_000:.1f} MB)")
            return out
        last_err = res.stderr[:400]
        log.warn(f"Encoder {encoder} gagal ({last_err[:150]}). Mencoba cadangan...")
    raise RuntimeError(f"Render akhir gagal: {last_err}")


def _template_metadata(narrations: list[dict]) -> str:
    joined = " ".join(n.get("narration", "") for n in narrations)[:600]
    titles = [
        "Alur Cerita Film Ini Bikin Merinding! | Recap Lengkap",
        "Ending-nya Nggak Ketebak! Recap Film Terbaik",
        "Film Ini Punya Plot Twist Gila! | Alur Cerita",
        "Dari Awal Sampai Akhir, Film Ini Bikin Tegang! | Recap",
        "Wajib Nonton Sebelum Nonton Filmnya! | Review & Recap",
    ]
    lines = ["=== 5 JUDUL ===\n"] + [f"{i+1}. {t}" for i, t in enumerate(titles)]
    lines += ["\n=== DESKRIPSI SEO ===\n",
              f"Di video ini kita bahas alur cerita film selengkapnya. {joined}\n"
              "Tonton sampai habis karena ending-nya tidak terduga. "
              "Jangan lupa like, komentar, dan subscribe!",
              "\n=== HASHTAG ===\n#alurcerita #recapfilm #reviewfilm #alurceritafilm #film",
              "\n=== PROMPT THUMBNAIL ===\n",
              "Thumbnail YouTube sinematik: wajah karakter utama terkejut di tengah, "
              "latar adegan paling dramatis film, teks besar kuning 'PLOT TWIST!', "
              "kontras tinggi, gaya poster film."]
    return "\n".join(lines)


def make_upload_metadata(narrations: list[dict], out_path: str | Path,
                         api_key: str = "", model: str = "gemini-2.5-flash",
                         logger: Logger | None = None) -> Path:
    log = logger or Logger()
    text = ""
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = ("Buatkan paket upload YouTube Bahasa Indonesia dari naskah recap ini: "
                      "5 judul clickbait (tapi jujur, tidak bohong), 1 deskripsi SEO, "
                      "10 hashtag, 1 prompt thumbnail.\n\n"
                      + "\n".join(n.get("narration", "") for n in narrations)[:6000])
            resp = client.models.generate_content(model=model, contents=prompt)
            text = (resp.text or "").strip()
        except Exception as e:
            log.warn(f"Metadata Gemini gagal ({e}). Memakai template.")
    if not text:
        text = _template_metadata(narrations)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    log.log(f"Paket upload tersimpan: {out.name}")
    return out
