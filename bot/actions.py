"""Acciones ejecutables cuando una condicion se cumple.

Cada accion recibe: los indicadores instanciados, la condicion que disparo,
los resultados actuales y los previos. Para agregar una accion nueva, basta
definir la funcion y registrarla en ACCIONES.
"""

from . import notify


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


ACCIONES = {
    "telegram_transicion": telegram_transicion,
    "telegram_informe": telegram_informe,
    "print": imprimir,
}


def ejecutar(nombre, indicadores, condicion, actual, previo):
    """Ejecuta una accion por nombre si esta registrada."""
    accion = ACCIONES.get(nombre)
    if accion is None:
        print(f"[WARN] Accion desconocida: {nombre}")
        return
    accion(indicadores, condicion, actual, previo)
