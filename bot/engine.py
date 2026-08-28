"""Motor global: junta los datos de todos los indicadores, evalua las condiciones
declarativas de config.CONDICIONES y ejecuta las acciones que correspondan.

Flujo por ejecucion:
  1) preparar_datos -> velas + precio spot en vivo.
  2) compute() de cada indicador (bot/indicators/<nombre>.py).
  3) render() de cada indicador (reporte en consola).
  4) evaluar cada condicion contra resultados actuales vs previos.
  5) ejecutar las acciones de las condiciones que se cumplan.
  6) persistir los resultados actuales (last_state.json) para la proxima corrida.
"""

import json
import os
import sys
import time
from datetime import datetime

from .actions import ejecutar
from .conditions import evaluar
from .config import CONDICIONES, CONFIG, INDICADORES, CYAN, RESET
from .data import preparar_datos
from .indicators import cargar_indicadores


def load_estado():
    """Lee los resultados previos persistidos (None si no existen o son ilegibles)."""
    try:
        with open(CONFIG["state_file"], "r", encoding="utf-8") as f:
            return json.load(f).get("indicadores")
    except (OSError, ValueError):
        return None


def save_estado(resultados):
    """Persiste los resultados actuales para detectar transiciones entre reinicios."""
    try:
        with open(CONFIG["state_file"], "w", encoding="utf-8") as f:
            json.dump({"indicadores": resultados}, f, default=str)
    except OSError:
        print("[WARN] No se pudo guardar el estado en last_state.json")


def run_analysis():
    """Una ejecucion completa: datos -> indicadores -> condiciones -> acciones."""
    indicadores = cargar_indicadores(INDICADORES)
    df = preparar_datos(CONFIG)
    resultados = {}
    for nombre, ind in indicadores.items():
        r = ind.compute(df)
        resultados[nombre] = r
        ind.render(r)
    previo = load_estado()
    for condicion in CONDICIONES:
        if evaluar(condicion, resultados, previo):
            print(f"[CONDICION] {condicion['nombre']} -> acciones: {', '.join(condicion['acciones'])}")
            for accion in condicion["acciones"]:
                ejecutar(accion, indicadores, condicion, resultados, previo)
    save_estado(resultados)
    return resultados


def engine():
    """Bucle del bot: corre el analisis cada vez que se cierra una vela."""
    os.system("")
    done = ()
    print(f"\n{CYAN}ML RSI [BQ] activo | {CONFIG['symbol']} | {CONFIG['timeframe']}{RESET}\n")
    while True:
        now = datetime.now()
        key = (now.year, now.month, now.day, now.hour)
        try:
            if now.minute <= 1 and key != done:
                print(f"{CYAN}[RUN]{RESET} {now:%Y-%m-%d %H:%M:%S} | ultima vela cerrada...")
                run_analysis()
                done = key
                print(f"[INFO] Ok. Durmiendo ~58 min ({CONFIG['sleep_after']}s)\n")
                time.sleep(CONFIG["sleep_after"])
            else:
                time.sleep(CONFIG["sleep_poll"])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(f"[ERROR] {now:%Y-%m-%d %H:%M:%S} | {type(e).__name__}: {e} | Reintento en {CONFIG['sleep_retry']}s\n")
            time.sleep(CONFIG["sleep_retry"])


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        engine()
    except KeyboardInterrupt:
        print("\n[INFO] Motor detenido por el usuario.")
        sys.exit(0)
