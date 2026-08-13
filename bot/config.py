"""Configuracion global del bot y condiciones declarativas.

El motor (bot/engine.py) corre todos los indicadores listados en INDICADORES y
luego evaluara las CONDICIONES: si se cumplen, ejecuta las acciones asociadas.
"""

import os
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CBA_TZ = timezone(timedelta(hours=-3))  # Cordoba, Argentina (UTC-3 fijo, sin horario de verano)


def hora_cba():
    """Hora actual en Cordoba, Argentina, formato 'HH:MM AM/PM'."""
    return datetime.now(CBA_TZ).strftime("%H:%M %p")

CONFIG = dict(
    symbol="BTC/USDT",
    tv_symbol="BINANCE:BTCUSDT",  # simbolo TradingView usado para el precio spot
    timeframe="1h",
    fetch_limit=10000,
    page=1000,
    eval_live=True,  # True = barra actual (como Pine), False = ultima cerrada
    sleep_after=3480,
    sleep_retry=60,
    sleep_poll=30,
    state_file=os.path.join(PROJECT_ROOT, "last_state.json"),
)

# Indicadores que se calculan en cada ejecucion (cada uno en bot/indicators/<nombre>.py).
INDICADORES = ["ml_rsi", "rsi14"]

# Condiciones declarativas. Tipos soportados:
#   cambio_estado : se cumple si el valor del campo cambio entre la ejecucion
#                   anterior y la actual. Filtros opcionales: desde (valor previo
#                   exigido) y hacia (valores de destino permitidos).
#   mayor_que / menor_que : compara el campo con "valor".
#   igual                 : campo == valor.
#   dentro_de_rango       : min <= campo <= max.
#   fuera_de_rango        : campo < min or campo > max.
CONDICIONES = [
    dict(
        nombre="Cambio de color de la senal",
        tipo="cambio_estado",
        indicador="ml_rsi",
        campo="estado",
        desde=None,  # None = se dispara ante cualquier cambio
        hacia=("Verde", "Gris", "Rojo"),
        acciones=["telegram_transicion", "telegram_informe"],
        activo=True,
    ),
    dict(
        nombre="RSI suavizado en sobrecompra",
        tipo="mayor_que",
        indicador="ml_rsi",
        campo="smooth",
        valor=70.0,
        acciones=["telegram_informe"],
        activo=False,
    ),
    dict(
        nombre="RSI suavizado en sobreventa",
        tipo="menor_que",
        indicador="ml_rsi",
        campo="smooth",
        valor=30.0,
        acciones=["telegram_informe"],
        activo=False,
    ),
    dict(
        nombre="RSI 14: sobrecomprado",
        tipo="mayor_que",
        indicador="rsi14",
        campo="rsi",
        valor=70.0,
        acciones=["telegram_informe"],
        activo=False,
    ),
    dict(
        nombre="RSI 14: divergencia alcista",
        tipo="igual",
        indicador="rsi14",
        campo="bull_div",
        valor=True,
        acciones=["telegram_informe"],
        activo=False,
    ),
]

# ------- Colores ANSI -------
# Solo se aplican cuando la salida es una terminal real; si esta redirigida o
# capturada (GitHub Actions, tuberias) quedan vacios para no imprimir codigos raros.
import os
import sys


def _soporta_color():
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                return True
            return False
        except Exception:
            return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


if _soporta_color():
    GREEN, RED, GRAY, CYAN, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[96m", "\033[0m"
else:
    GREEN, RED, GRAY, CYAN, RESET = "", "", "", "", ""
