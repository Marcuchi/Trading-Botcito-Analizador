"""Envia a Telegram un mensaje de PRUEBA con los datos del analisis actual."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml_rsi_pro import (  # noqa: E402
    CONFIG,
    build_alert_message,
    classify,
    fetch_ohlcv,
    indicators,
    last_closed,
    thresholds,
)
from notify import send_telegram  # noqa: E402

if __name__ == "__main__":
    full = indicators(fetch_ohlcv())
    if full.empty:
        print("[ERROR] Sin velas disponibles.")
        sys.exit(1)
    closed = last_closed(full)
    base = full if CONFIG["eval_live"] else closed
    live = base.iloc[-1]
    up, lo = thresholds(base["smooth"].tail(CONFIG["ml_window"]))
    state = classify(live["smooth"], up, lo)
    msg = build_alert_message(state, live, up, lo, header="PRUEBA DE CONEXION")
    print(msg)
    print("Enviado:", send_telegram(msg))
