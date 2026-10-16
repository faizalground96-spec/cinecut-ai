# 🎬 CineCut AI — Pembuat Video Recap / Review Film Otomatis

Masukkan file film → CineCut AI otomatis: ambil transkrip → AI pilih adegan terbaik → potong klip → AI tulis narasi → ubah narasi jadi suara → gabung + efek + subtitel → render video siap upload (YouTube / TikTok / Reels).

Dokumen arsitektur lengkap ada di [plan.md](plan.md) — itu plan asli yang dipakai membangun proyek ini.

## Cara Pakai (Paling Gampang — Windows)

1. Unduh dari halaman **Releases**: file `CineCutAI-Portable-Windows.zip`
2. Ekstrak (klik kanan → Extract All)
3. Jalankan `CineCutAI.exe`
4. Pilih file film → tempel **Kunci Gemini** → pilih gaya + rasio → tekan **MULAI BUAT VIDEO**

> **Kunci Gemini:** didapat gratis / berbayar di https://ai.studio.google.com
> Kunci hanya diisi di dalam aplikasi, tidak pernah dikirim ke tempat lain selain Gemini API.
> Tanpa kunci pun aplikasi tetap jalan (memakai pembagian adegan + narasi cadangan), tapi hasilnya tidak sebagus pakai AI.

## Cara Pakai (Dari Kode — Windows)

Klik dua kali `scripts/setup_windows.bat`, lalu klik shortcut **CineCut AI** di Desktop.

Atau manual:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

Mode baris perintah:

```bat
python -m src.main --input film.mp4 --durasi 10 --rasio 16:9 --gaya Sinematik
```

## Alur 8 Tahap

1. **Input Film** — validasi file + baca metadata (ffprobe)
2. **Transkrip** — subtitle tertanam → .srt eksternal → Faster-Whisper (cadangan)
3. **AI Pilih Adegan** — Gemini + JSON ketat (kalau gagal, pakai pembagian cadangan)
4. **Potong Klip** — FFmpeg, suara asli film dilemahkan jadi ambiens -25 dB
5. **AI Buat Narasi** — Gemini nonton klip langsung, batas kata `Wmax = floor(Dklip × 2.5)`
6. **Suara (TTS)** — Gemini TTS, cadangan Edge-TTS (ArdiNeural / GadisNeural) + subtitel `.ass`
7. **Gabung** — sinkron durasi `S = Dklip / Dsuara` (filter `setpts`), transisi fade, ducking BGM, burn-in subtitel
8. **Render + Paket Upload** — NVENC / AMF / QSV / libx264, rasio 16:9 atau 9:16 (latar blur), + `upload_metadata.txt` (5 judul, deskripsi SEO, hashtag, prompt thumbnail)

## ⚠️ Penting Soal Hak Cipta — Baca Dulu

Efek cermin (flip) dan zoom di aplikasi ini adalah **efek visual saja**.
Efek tersebut **BUKAN jaminan lolos Content ID / Fair Use**.
Gunakan klip seperlunya, tambahkan narasi / ulasan orisinalmu, dan patuhi aturan platform tempat kamu upload.

## File & Folder

```
cinecut-ai/
├── assets/          # font, SFX, BGM, ikon
├── bin/             # ffmpeg.exe + ffprobe.exe (diunduh otomatis saat build)
├── src/             # kode: main.py, config.py, gui/, pipeline/step1..step8, utils/
├── workspace/       # folder kerja (klip, suara, subtitel, hasil)
├── scripts/         # setup_windows.bat + build_exe.py
├── plan.md          # plan asli
└── requirements.txt
```

## Bikin EXE Sendiri

```bat
python scripts/build_exe.py
```

Hasilnya di `dist/CineCutAI/CineCutAI.exe`. GitHub Actions juga otomatis membangun EXE setiap push ke `main` dan membuat Release setiap tag `v*` (misal `v1.0.0`).
