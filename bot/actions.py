"""Acciones ejecutables cuando una condicion se cumple.

Cada accion recibe: los indicadores instanciados, la condicion que disparo,
los resultados actuales y los previos. Para agregar una accion nueva, basta
definir la funcion y registrarla en ACCIONES.
"""

from . import notify
from .config import CONFIG


def telegram_transicion(indicadores, condicion, actual, previo):
    """Notifica por Telegram el cambio de estado con su transicion."""
    ind = indicadores[condicion["indicador"]]
    r = actual[condicion["indicador"]]
    prev_val = (previo.get(condicion["indicador"], {}) or {}).get(condicion["campo"], "?")
    cur_val = r.get(condicion["campo"], "?")
    msg = ind.mensaje(r, header=f"Transicion: {prev_val} -> {cur_val}")
    if notify.send_telegram(msg):
        print(f"[TELEGRAM] Transicion enviada: {prev_val} -> {cur_val}")


def telegram_informe(indicadores, condicion, actual, previo):
    """Notifica por Telegram el informe del indicador que disparo la condicion."""
    ind = indicadores[condicion["indicador"]]
    r = actual[condicion["indicador"]]
    if notify.send_telegram(ind.mensaje(r)):
        print("[TELEGRAM] Informe enviado")


def imprimir(indicadores, condicion, actual, previo):
    """Imprime en consola el informe del indicador (sin notificar)."""
    ind = indicadores[condicion["indicador"]]
    r = actual[condicion["indicador"]]
    print(ind.mensaje(r))


def informe_completo(indicadores, actual):
    """Arma UN mensaje con todos los indicadores sobre la misma barra y plataforma."""
    titulos = {
        "ml_rsi": "ML RSI",
        "rsi14": "RSI 14",
        "rsi_fractal": "RSI Fractal Energy",
        "adx": "ADX",
    }
    sep = "-------"
    barra = next(
        (r.get("barra") for r in actual.values() if isinstance(r, dict) and "barra" in r),
        None,
    )
    lines = [f"Datos : {CONFIG['tv_symbol']} / {CONFIG['timeframe']}"]
    if barra:
        lines.append(f"Barra : {barra}")
    for nombre, ind in indicadores.items():
        r = actual.get(nombre)
        if not r:
            continue
        cuerpo = ind.mensaje(r).split("\n")
        if len(cuerpo) > 1:
            cuerpo = cuerpo[1:]  # quita el encabezado propio de cada indicador
        lines.append(sep)
        lines.append(f"{titulos.get(nombre, ind.nombre)}:")
        lines.extend(cuerpo)
    return "\n".join(lines)


def telegram_informe_completo(indicadores, condicion, actual, previo):
    """Notifica por Telegram un unico mensaje con todos los indicadores juntos."""
    if notify.send_telegram(informe_completo(indicadores, actual)):
        print("[TELEGRAM] Informe completo enviado")


ACCIONES = {
    "telegram_transicion": telegram_transicion,
    "telegram_informe": telegram_informe,
    "telegram_informe_completo": telegram_informe_completo,
    "print": imprimir,
}


def ejecutar(nombre, indicadores, condicion, actual, previo):
    """Ejecuta una accion por nombre si esta registrada."""
    accion = ACCIONES.get(nombre)
    if accion is None:
        print(f"[WARN] Accion desconocida: {nombre}")
        return
    accion(indicadores, condicion, actual, previo)
