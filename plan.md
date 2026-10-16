# 🎬 CineCut AI (Auto-Movie Recap & Review Generator for Windows)

**CineCut AI** adalah perangkat lunak desktop berbasis Windows yang mengotomatiskan seluruh proses pembuatan konten *movie recap* atau *review film* mulai dari bahan mentah (file film utuh) hingga menjadi video siap unggah (YouTube, TikTok, Reels) menggunakan kekuatan **Google AI Studio (Gemini API)** dan **FFmpeg**.

---

## 1. Arsitektur Teknologi (Tech Stack)

Agar aplikasi berjalan kencang di Windows, mudah diinstal oleh pengguna awam, dan memanfaatkan penuh ekosistem Google AI Studio, berikut adalah teknologi yang digunakan:

| Komponen | Teknologi / Library | Alasan Pemilihan |
| :--- | :--- | :--- |
| **Bahasa Pemrograman** | **Python 3.11+** | Ekosistem AI, audio, dan pemrosesan video paling matang. |
| **Antarmuka (GUI Windows)** | **CustomTkinter** atau **PyQt6** | Tampilan modern (Dark Mode), ringan, dan mudah dibungkus menjadi `.exe`. |
| **Otak AI (LLM & Multimodal)** | **Google AI Studio (`google-genai` SDK)** | Konteks hingga 2 Juta token (`gemini-2.5-flash` / `gemini-2.5-pro`), mendukung pemahaman video langsung (Multimodal) & *Structured JSON Output*. |
| **Text-to-Speech (TTS)** | **Gemini 2.5 Native Audio TTS** + **Edge-TTS (Fallback)** | Menghasilkan suara narator yang natural dengan intonasi emosional, dilengkapi opsi suara Bahasa Indonesia (`ArdiNeural` / `GadisNeural`). |
| **Ekstraksi Transkrip/Sub** | **FFprobe / FFmpeg** + **Faster-Whisper** | Mengekstrak *embedded subtitle* (`.srt`/`.ass`) secara instan, atau transkripsi suara otomatis jika film tidak memiliki subtitel. |
| **Video & Audio Engine** | **FFmpeg (dengan akselerasi GPU NVENC/AMF/QSV)** | Pemotongan klip presisi tinggi, *rendering* cepat, efek transisi (`xfade`), *audio ducking*, dan *burn-in* subtitel `.ass`. |
| **Distribusi Windows** | **PyInstaller** + **Inno Setup** | Mengubah seluruh skrip Python dan *dependencies* menjadi 1 file `CineCut_Setup.exe` standar Windows. |

---

## 2. Alur Kerja Sistem (8 Tahap Utama)

```
[1. Input Film] ──► [2. Ekstrak Sub/Transkrip] ──► [3. Gemini Analisis & Pilih Klip]
                                                              │
[6. Generate TTS] ◄── [5. Gemini Buat Narasi Review] ◄── [4. FFmpeg Potong Klip]
        │
        ▼
[7. Komposisi: Klip + Suara + Subtitel + Efek/SFX] ──► [8. Render Video Siap Upload]
```

### Tahap 1: Input Film (Paste / Import Movie)
* **Input:** Pengguna melakukan *drag-and-drop* file film lokal (`.mp4`, `.mkv`, `.avi`) atau menempelkan path/URL video ke dalam aplikasi.
* **Proses Sistem:**
  * Sistem memvalidasi integritas file menggunakan `ffprobe`.
  * Membaca metadata video: durasi total, resolusi, *frame rate* (FPS), daftar *audio track*, dan daftar *subtitle track* yang tertanam di dalam kontainer video.

### Tahap 2: Ambil Transkrip / Subtitle
* **Proses Sistem (Prioritas Bertingkat):**
  1. **Jalur Cepat (Embedded Subtitle):** Jika file `.mkv`/`.mp4` memiliki track subtitel (Indonesia/Inggris), FFmpeg langsung mengekstraknya menjadi file `raw_subtitles.srt` dalam hitungan detik.
  2. **Jalur Eksternal:** Pengguna dapat memuat file `.srt` terpisah jika ada.
  3. **Jalur AI Speech-to-Text (Fallback):** Jika film sama sekali tidak memiliki subtitel, sistem mengekstrak audio (`16kHz mono .wav`) lalu memprosesnya menggunakan **Faster-Whisper** (lokal) atau mengunggah audio ke **Gemini API** untuk menghasilkan transkrip lengkap beserta *timestamp*.
* **Output:** File `transcript_clean.json` berisi daftar dialog dengan format `[id, start_time, end_time, text]`.

### Tahap 3: AI Analisis & Pilih Bagian Terbaik (Scene Selection)
* **Integrasi AI Studio:** Menggunakan model `gemini-2.5-flash` melalui SDK `google-genai`. Karena jendela konteks Gemini mencapai 1–2 juta token, seluruh isi subtitel film berdurasi 2–3 jam dapat dikirim sekaligus dalam **satu kali request**.
* **Cara Kerja Prompt & Schema:**
  * Sistem mengirim transkrip dengan instruksi: *"Analisis alur cerita film ini. Pilih 15–25 adegan kunci yang membangun struktur cerita utuh (Hook/Pembuka, Pengenalan Konflik, Klimaks, dan Twist/Ending) untuk video review berdurasi $N$ menit."*
  * Menggunakan fitur **Structured Outputs (`response_schema`)** agar Gemini wajib membalas dalam format JSON yang ketat:
    ```json
    [
      {
        "clip_id": 1,
        "phase": "HOOK",
        "start_time": "00:45:12.000",
        "end_time": "00:45:28.500",
        "scene_summary": "Karakter utama terjebak di ruangan terkunci",
        "dramatic_score": 9.5,
        "suggested_sfx": "suspense_riser"
      }
    ]
    ```

### Tahap 4: Pemotongan Klip Video (Pre-Cut Scenes)
* **Proses Sistem:**
  * Berdasarkan koordinat `start_time` dan `end_time` dari JSON Tahap 3, modul `VideoCutter` memanggil **FFmpeg** untuk memotong film asli menjadi potongan klip terpisah (`workspace/clips/clip_001.mp4`, `clip_002.mp4`, dst.).
  * **Pembersihan Visual:** Menghapus teks subtitel bawaan (jika *softsub*) dan membungkam suara asli film (atau menyimpannya di *channel* terpisah dengan volume rendah $-25\text{ dB}$ untuk ambiens).

### Tahap 5: AI Membuat Teks Narasi Review dari Potongan Klip (Multimodal)
Inilah keunggulan utama memotong klip terlebih dahulu sebelum membuat naskah:
* **Proses Sistem:**
  * Klip-klip yang sudah dipotong di Tahap 4 diunggah ke **Google AI Studio File API** (`client.files.upload`).
  * **Gemini Multimodal (`gemini-2.5-flash`)** *menonton langsung* potongan video tersebut (bukan sekadar membaca teks subtitel), sehingga AI tahu persis ekspresi wajah aktor, aksi visual di layar, dan durasi tiap klip.
  * AI diinstruksikan menulis narasi *review/recap* untuk setiap klip dengan batas jumlah kata yang disesuaikan dengan durasi klip:
    $$W_{\text{max}} = \lfloor D_{\text{clip}} \times 2.5 \rfloor$$
    *(Asumsi kecepatan bicara narator rata-rata adalah $2.5\text{ kata/detik}$).*
* **Output:** File `narration_script.json` yang memetakan setiap `clip_id` dengan teks narasi review yang sinkron secara visual dan durasi.

### Tahap 6: Generate Text-to-Voice (TTS) & Word Timestamps
* **Proses Sistem:**
  * Setiap segmen narasi dari Tahap 5 diubah menjadi file audio `.wav`/`.mp3`.
  * **Opsi Utama (Google AI Studio):** Menggunakan `gemini-2.5-flash-preview-tts` untuk menghasilkan suara dengan emosi yang sesuai konteks adegan (tegang, sedih, antusias).
  * **Opsi Alternatif (Cepat & Gratis):** Menggunakan `edge-tts` (`id-ID-ArdiNeural`) yang sekaligus menghasilkan metadata *WordBoundary* (detik ke berapa setiap kata diucapkan) untuk pembuatan subtitel dinamis bergaya TikTok/Reels.
* **Output:** File `voice_001.wav`, `voice_002.wav`, serta file subtitel `.ass` (Advanced SubStation Alpha) per segmen.

### Tahap 7: Penggabungan (Klip + Suara + Subtitel + Efek/Transisi/SFX)
Pada tahap ini, modul `ComposerEngine` menyatukan seluruh elemen secara otomatis:
1. **Sinkronisasi Durasi Otomatis (Auto Time-Stretch):**
   Jika durasi suara narasi ($D_{\text{audio}}$) sedikit berbeda dengan durasi klip video ($D_{\text{clip}}$), sistem menyesuaikan kecepatan pemutaran klip video menggunakan filter `setpts` di FFmpeg dengan faktor skala:
   $$S = \frac{D_{\text{clip}}}{D_{\text{audio}}}$$
   *(Jika klip terlalu panjang, klip dipercepat sedikit atau dipotong ujungnya agar pas 100% dengan kalimat narator).*
2. **Filter Anti-Copyright (Fair Use Protection):**
   * *Horizontal Flip* (pencerminan gambar opsional per beberapa klip).
   * *Dynamic Zoom/Crop* ($1.05\times$ hingga $1.10\times$) dan koreksi warna ringan (*Color Grading* LUT).
3. **Transisi & Sound Effects (SFX):**
   * Menambahkan transisi antar klip menggunakan filter `xfade` (fade, wipe, dissolve, glitch) dan menyisipkan file SFX (`whoosh.wav`, `boom.wav`, `riser.wav`) pada titik pergantian adegan sesuai label `suggested_sfx` dari Gemini.
4. **Audio Mixing & Auto-Ducking:**
   * Menggabungkan suara Narator ($0\text{ dB}$), Musik Latar/BGM ($-18\text{ dB}$), dan SFX ($-6\text{ dB}$) dengan filter `sidechaincompress` (volume musik otomatis mengecil saat narator berbicara).
5. **Burn-in Dynamic Subtitles:**
   * Merender subtitel format `.ass` dengan *font* tebal (misal: *Montserrat ExtraBold*), *outline* hitam, dan animasi *pop-up* per kata/frasa tepat di tengah-bawah layar.

### Tahap 8: Render Final & Paket Siap Upload
* **Proses Sistem:**
  * FFmpeg melakukan *rendering* akhir menggunakan *hardware acceleration* (`h264_nvenc` untuk NVIDIA, `h264_amf` untuk AMD, atau `libx264` untuk CPU) dalam rasio aspek pilihan pengguna: **16:9 (YouTube Landscape)** atau **9:16 (TikTok/Shorts/Reels Vertical dengan Blur Background)**.
  * Gemini menghasilkan file `upload_metadata.txt` yang berisi **5 Rekomendasi Judul Clickbait**, **Deskripsi Video SEO**, **Hashtags**, dan **Prompt Thumbnail**.

---

## 3. Spesifikasi Integrasi Google AI Studio (`google-genai`)

Aplikasi ini menggunakan SDK generasi terbaru dari Google: `google-genai`. Pengguna hanya perlu memasukkan `GEMINI_API_KEY` yang didapatkan gratis atau berbayar dari [ai.studio.google.com](https://ai.studio.google.com).

### Alur Panggilan API di Dalam Kode:
1. **Inisialisasi Klien:**
   ```python
   from google import genai
   from google.genai import types

   client = genai.Client(api_key=USER_API_KEY)
   ```
2. **Pemilihan Adegan dari Subtitel (Tahap 3):**
   Menggunakan `gemini-2.5-flash` dengan `response_mime_type="application/json"` dan `response_schema=SceneListSchema` untuk menjamin hasil potongan tidak pernah error saat diproses oleh FFmpeg.
3. **Pembuatan Naskah berbasis Video (Tahap 5):**
   Mengunggah klip hasil potongan ke File API (`client.files.upload(file="clip_001.mp4")`), lalu meminta Gemini membuat narasi yang mendeskripsikan sekaligus mengulas adegan tersebut secara sinematik, kemudian menghapus file sementara di server dengan `client.files.delete()`.

---

## 4. Struktur Direktori Repositori GitHub

Berikut adalah rancangan struktur folder repositori yang rapi dan modular:

```text
cinecut-ai/
├── assets/
│   ├── fonts/                  # Font untuk subtitle (Montserrat-Bold.ttf, dll)
│   ├── sfx/                    # Efek suara (whoosh.mp3,vine_boom.mp3, suspense.mp3)
│   ├── bgm/                    # Musik latar bebas royalti (tegang, sedih, aksi)
│   └── icons/                  # Ikon aplikasi (.ico untuk Windows)
├── bin/                        # Tempat binary eksternal (ffmpeg.exe, ffprobe.exe)
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point aplikasi & inisialisasi GUI
│   ├── config.py               # Pengaturan API Key, resolusi, preset efek
│   ├── gui/
│   │   ├── app_window.py       # Antarmuka utama (CustomTkinter)
│   │   ├── progress_panel.py   # Log & progress bar 8 tahapan
│   │   └── preview_player.py   # Pemutar pratinjau hasil video
│   ├── pipeline/
│   │   ├── step1_ingest.py     # Validasi file film & pembacaan metadata
│   │   ├── step2_subtitle.py   # Ekstraksi SRT / Faster-Whisper STT
│   │   ├── step3_ai_selector.py# Gemini API: Analisis transkrip & pilih timestamp
│   │   ├── step4_cutter.py     # FFmpeg: Pemotongan klip presisi
│   │   ├── step5_ai_narrator.py# Gemini Multimodal: Nonton klip & tulis narasi review
│   │   ├── step6_tts.py        # Gemini TTS / Edge-TTS + generator subtitle .ass
│   │   ├── step7_composer.py   # FFmpeg: Gabung klip, suara, subtitel, transisi, SFX
│   │   └── step8_exporter.py   # Render final MP4 & generator judul/deskripsi SEO
│   └── utils/
│       ├── ffmpeg_helper.py    # Wrapper command-line FFmpeg & deteksi GPU
│       ├── time_parser.py      # Konversi format waktu SRT ke detik/milidetik
│       └── logger.py           # Sistem pencatatan log error & proses
├── workspace/                  # Folder kerja sementara per proyek (otomatis dibersihkan)
│   ├── clips/
│   ├── audio/
│   ├── subtitles/
│   └── output/
├── scripts/
│   ├── setup_windows.bat       # Skrip instalasi otomatis untuk developer
│   └── build_exe.py            # Skrip PyInstaller untuk membuat file .exe
├── .env.example                # Contoh konfigurasi GEMINI_API_KEY
├── requirements.txt            # Daftar pustaka Python
├── plan.md                     # Dokumen arsitektur sistem (File ini)
└── README.md                   # Panduan penggunaan repositori
```

---

## 5. Strategi Instalasi di Windows (User-Friendly)

Agar software ini mudah diinstal di Windows tanpa mengharuskan pengguna menginstal Python atau mengonfigurasi `PATH` FFmpeg secara manual, kita menyediakan **2 metode distribusi**:

### Metode A: Portable / One-Click Installer (`.exe`) — *Untuk Pengguna Umum*
1. **Bundling FFmpeg:** File `ffmpeg.exe` dan `ffprobe.exe` disertakan langsung di dalam folder `bin/`.
2. **Kompilasi PyInstaller:** Menjalankan `pyinstaller --noconfirm --onedir --windowed --icon=assets/icons/app.ico src/main.py` untuk membungkus seluruh kode Python dan antarmuka GUI menjadi `CineCutAI.exe`.
3. **Inno Setup Wizard:** Membungkus folder hasil PyInstaller menjadi satu file installer `CineCutAI_Installer_v1.0.exe`. Saat pengguna menginstal, aplikasi otomatis membuat *Shortcut* di Desktop dan Start Menu Windows.

### Metode B: Instalasi via GitHub (`setup_windows.bat`) — *Untuk Developer/Modder*
Pengguna cukup mengunduh (*clone/download ZIP*) repositori dan mengklik dua kali file `setup_windows.bat` yang berisi otomatisasi berikut:
1. Membuat *Virtual Environment* (`python -m venv venv`).
2. Mengunduh otomatis `ffmpeg-release-essentials.zip` untuk Windows dan mengekstraknya ke folder `bin/`.
3. Menginstal seluruh pustaka di `requirements.txt` (`google-genai`, `customtkinter`, `edge-tts`, `faster-whisper`, `pydantic`).
4. Membuat shortcut `Run_CineCut.bat` di layar Desktop.

---

## 6. Rencana Pengembangan Bertahap (Roadmap)

* **Fase 1 (Core CLI Prototype):** Membangun skrip Python baris perintah (CLI) yang menjalankan Tahap 1 hingga Tahap 8 secara berurutan dari 1 file film menjadi 1 video selesai.
* **Fase 2 (Efek, SFX & Anti-Copyright):** Menyempurnakan skrip filter kompleks FFmpeg untuk *auto-ducking* BGM, penyisipan SFX otomatis, dan *burn-in* subtitel animasi `.ass`.
* **Fase 3 (GUI Desktop Windows):** Membangun tampilan visual menggunakan CustomTkinter lengkap dengan pengaturan API Key Google AI Studio, pilihan gaya narasi (Santai, Sinematik, Komedi, Tegang), dan pilihan rasio video (16:9 / 9:16).
* **Fase 4 (Packaging Windows):** Menguji dan membungkus aplikasi menjadi file installer `.exe`.