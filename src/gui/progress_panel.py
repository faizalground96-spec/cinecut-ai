"""Panel progres 8 tahap + kotak log (dipakai jendela utama)."""
from __future__ import annotations

try:
    import customtkinter as ctk
except ImportError:  # cadangan: tkinter biasa
    import tkinter as ctk  # type: ignore

STAGES = [
    "1. Input Film", "2. Transkrip / Subtitle", "3. AI Pilih Adegan",
    "4. Potong Klip", "5. AI Buat Narasi", "6. Suara (TTS) + Subtitel",
    "7. Gabung + Efek", "8. Render + Paket Upload",
]


class ProgressPanel:
    """Panel kecil: label tahap + progress bar + log."""

    def __init__(self, parent):
        self.label = ctk.CTkLabel(parent, text="Siap — pilih film lalu tekan MULAI")
        self.label.pack(pady=(8, 2), anchor="w")
        try:
            self.bar = ctk.CTkProgressBar(parent)
            self.bar.set(0)
            self.bar.pack(fill="x", padx=4, pady=4)
        except Exception:
            self.bar = None
        try:
            self.log_box = ctk.CTkTextbox(parent, height=180)
            self.log_box.pack(fill="both", expand=True, padx=4, pady=4)
        except Exception:
            self.log_box = None

    def set_stage(self, idx: int, text: str = "") -> None:
        name = STAGES[idx] if 0 <= idx < len(STAGES) else "Selesai"
        self.label.configure(text=f"{name} {text}")
        if self.bar is not None:
            self.bar.set((idx + 1) / len(STAGES))

    def append_log(self, line: str) -> None:
        if self.log_box is None:
            return
        try:
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
        except Exception:
            pass
