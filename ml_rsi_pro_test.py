"""
Script de PRUEBA: cadencia de 1 minuto para validar la pipeline ML RSI Pro
sin esperar 58 min. Reutiliza toda la logica de ml_rsi_pro.py.

Uso:
    python ml_rsi_pro_test.py          # bucle: 1 analisis por minuto
    python ml_rsi_pro_test.py --once   # 1 solo analisis y sale
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml_rsi_pro import CONFIG, run_analysis, CYAN, RESET  # noqa: E402

TEST = dict(CONFIG, sleep_after=10, sleep_retry=10, sleep_poll=1)


def test_engine():
    """Ejecuta el analisis en los segundos 0-5 de cada minuto, 1 vez por minuto."""
    done = ()
    print(f"\n{CYAN}[PRUEBA] Cadencia: cada minuto | {CONFIG['symbol']} | {CONFIG['timeframe']}{RESET}\n")
    while True:
        now = datetime.now()
        key = (now.year, now.month, now.day, now.hour, now.minute)
        try:
            if now.second <= 5 and key != done:
                print(f"{CYAN}[RUN]{RESET} {now:%Y-%m-%d %H:%M:%S} | Analizando...")
                run_analysis()
                done = key
                print(f"[INFO] Ok. Durmiendo ~50s\n")
                time.sleep(TEST["sleep_after"])
            else:
                time.sleep(TEST["sleep_poll"])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(f"[ERROR] {now:%Y-%m-%d %H:%M:%S} | {type(e).__name__}: {e} | Reintento en {TEST['sleep_retry']}s\n")
            time.sleep(TEST["sleep_retry"])


if __name__ == "__main__":
    os.system("")
    if "--once" in sys.argv:
        try:
            run_analysis()
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            sys.exit(1)
        sys.exit(0)
    try:
        test_engine()
    except KeyboardInterrupt:
        print("\n[INFO] Motor de prueba detenido por el usuario.")
        sys.exit(0)
