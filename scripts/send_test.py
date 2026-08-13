"""Envia a Telegram un mensaje de PRUEBA con los datos del analisis actual.

Uso: python scripts/send_test.py (desde la raiz del proyecto)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import CONFIG, INDICADORES  # noqa: E402
from bot.data import preparar_datos  # noqa: E402
from bot.indicators import cargar_indicadores  # noqa: E402
from bot.notify import send_telegram  # noqa: E402

if __name__ == "__main__":
    indicadores = cargar_indicadores(INDICADORES)
    df = preparar_datos(CONFIG)
    for nombre, ind in indicadores.items():
        resultado = ind.compute(df)
        msg = ind.mensaje(resultado, header="PRUEBA DE CONEXION")
        print(msg)
        print(f"[{nombre}] Enviado:", send_telegram(msg))
