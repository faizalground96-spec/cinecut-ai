"""Jendela utama CineCut AI (CustomTkinter, Dark Mode).

Bahasa Indonesia sederhana. Kolom API key hanya untuk ditempel di aplikasi
— tidak disimpan ke GitHub, tidak dikirim ke mana pun selain Gemini API.
"""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog

try:
    import customtkinter as ctk
    _HAS_CTK = True
except ImportError:
    import tkinter as ctk  # type: ignore
    _HAS_CTK = False

from ..config import Config
from ..utils.logger import Logger
from .progress_panel import ProgressPanel
from .preview_player import open_video


def launch_gui(cfg: Config | None = None) -> None:
    cfg = cfg or Config.load()
    if _HAS_CTK:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
    else:
        root = ctk.Tk()
    root.title("CineCut AI — Pembuat Video Recap Film Otomatis")
    root.geometry("720x640")

    def add_label(text: str):
        lbl = ctk.CTkLabel(root, text=text)
        lbl.pack(anchor="w", padx=12, pady=(8, 0))
        return lbl

    add_label("1. Pilih file film (.mp4 / .mkv / .avi)")
    film_var = ctk.StringVar(value="")
    film_entry = ctk.CTkEntry(root, textvariable=film_var, width=520)
    film_entry.pack(padx=12, pady=4, anchor="w")

    def pick_film():
        p = filedialog.askopenfilename(
            title="Pilih file film",
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov *.webm"), ("Semua", "*.*")])
        if p:
            film_var.set(p)

    ctk.CTkButton(root, text="Cari File Film...", command=pick_film).pack(
        padx=12, pady=2, anchor="w")

    add_label("2. Kunci Gemini (dari ai.studio.google.com) — boleh kosong, nanti pakai cadangan")
    key_var = ctk.StringVar(value=cfg.api_key)
    ctk.CTkEntry(root, textvariable=key_var, show="*", width=520).pack(
        padx=12, pady=4, anchor="w")

    add_label("3. Gaya narasi")
    style_var = ctk.StringVar(value=cfg.style)
    ctk.CTkOptionMenu(root, variable=style_var,
                      values=["Santai", "Sinematik", "Komedi", "Tegang"]).pack(
        padx=12, pady=4, anchor="w")

    add_label("4. Rasio video hasil")
    aspect_var = ctk.StringVar(value=cfg.aspect)
    ctk.CTkOptionMenu(root, variable=aspect_var, values=["16:9", "9:16"]).pack(
        padx=12, pady=4, anchor="w")

    add_label("5. Target durasi video (menit)")
    dur_var = ctk.StringVar(value=str(cfg.target_minutes))
    ctk.CTkEntry(root, textvariable=dur_var, width=120).pack(padx=12, pady=4, anchor="w")

    flip_var = ctk.BooleanVar(value=cfg.flip_enabled)
    try:
        ctk.CTkCheckBox(root, text="Aktifkan efek cermin (opsional, BUKAN jaminan lolos hak cipta)",
                        variable=flip_var).pack(padx=12, pady=4, anchor="w")
    except Exception:
        pass

    panel = ProgressPanel(root)
    status = ctk.CTkLabel(root, text="")
    status.pack(padx=12, pady=4, anchor="w")

    def run():
        film = film_var.get().strip()
        if not film or not Path(film).exists():
            status.configure(text="Pilih file film dulu ya.")
            return
        try:
            cfg.target_minutes = float(dur_var.get())
        except ValueError:
            cfg.target_minutes = 10.0
        cfg.api_key = key_var.get().strip()
        cfg.style = style_var.get()
        cfg.aspect = aspect_var.get()
        cfg.flip_enabled = bool(flip_var.get())
        logger = Logger(on_line=lambda line: panel.append_log(line))
        panel.set_stage(0, "— mulai...")
        from ..pipeline.run_pipeline import run_pipeline
        try:
            result = run_pipeline(cfg, film, logger=logger)
            panel.set_stage(7, "— selesai!")
            status.configure(text=f"Selesai! Video: {result['video']}")
            try:
                open_video(result["video"])
            except Exception:
                pass
        except Exception as e:
            status.configure(text=f"Gagal: {e}")
            logger.error(str(e))

    ctk.CTkButton(root, text="▶ MULAI BUAT VIDEO", command=lambda: threading.Thread(
        target=run, daemon=True).start()).pack(padx=12, pady=10, anchor="w")
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
