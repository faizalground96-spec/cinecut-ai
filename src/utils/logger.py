"""Pencatatan log sederhana: ke layar + ke file (opsional)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


class Logger:
    def __init__(self, log_file: str | Path | None = None,
                 on_line: Callable[[str], None] | None = None):
        self.log_file = Path(log_file) if log_file else None
        self.on_line = on_line

    def log(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if self.on_line:
            try:
                self.on_line(line)
            except Exception:
                pass
        if self.log_file:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def error(self, msg: str) -> None:
        self.log(f"ERROR: {msg}")

    def warn(self, msg: str) -> None:
        self.log(f"PERINGATAN: {msg}")
