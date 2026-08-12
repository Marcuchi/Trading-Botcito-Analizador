"""Envio de alertas via Telegram Bot API.

Como configurar:
1) Crea un bot con @BotFather en Telegram y obten el token (ej: 123456:ABC...).
2) Obten tu chat_id: enviate un mensaje al bot y luego visita
   https://api.telegram.org/bot<TOKEN>/getUpdates ; el chat id aparece en "chat":{"id":...}.
3) Exporta las variables de entorno antes de ejecutar:
   set TELEGRAM_TOKEN=123456:ABC...      (Windows)
   set TELEGRAM_CHAT_ID=123456789
   o en Linux: export TELEGRAM_TOKEN=... / export TELEGRAM_CHAT_ID=...
"""

import os

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _load_env():
    """Carga credenciales desde .env (local) sin pisar variables ya definidas."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
                  encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def send_telegram(message):
    """Envia un mensaje de texto a uno o varios chats. Retorna True si todos se enviaron.
    TELEGRAM_CHAT_ID acepta varios ids separados por coma o punto y coma."""
    _load_env()
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    raw = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    chat_ids = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    if not token or not chat_ids:
        print("[TELEGRAM] Faltan TELEGRAM_TOKEN y TELEGRAM_CHAT_ID (variables o .env).")
        return False
    ok = True
    for chat_id in chat_ids:
        try:
            resp = requests.post(
                TELEGRAM_API.format(token=token),
                json={"chat_id": chat_id, "text": message},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            ok = False
            print(f"[TELEGRAM] Error enviando a {chat_id}: {type(e).__name__}: {e}")
    return ok
