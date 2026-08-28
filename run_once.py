"""Entrada unica: corre 1 analisis y sale. Usada por GitHub Actions (cron horario)."""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.engine import run_analysis  # noqa: E402

if __name__ == "__main__":
    try:
        run_analysis()
        print("[OK] Analisis completado.")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        sys.exit(1)
