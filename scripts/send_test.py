"""Envia a Telegram un mensaje de PRUEBA consolidado con todos los indicadores.

Uso: python scripts/send_test.py (desde la raiz del proyecto)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.actions import informe_completo  # noqa: E402
from bot.config import CONFIG, INDICADORES  # noqa: E402
from bot.data import preparar_datos  # noqa: E402
from bot.indicators import cargar_indicadores  # noqa: E402
from bot.notify import send_telegram  # noqa: E402

if __name__ == "__main__":
    indicadores = cargar_indicadores(INDICADORES)
    df = preparar_datos(CONFIG)
    resultados = {}
    for nombre, ind in indicadores.items():
        resultados[nombre] = ind.compute(df)
    msg = informe_completo(indicadores, resultados)
    print(msg)
    print("[TELEGRAM] Enviado:", send_telegram(msg))
