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


def informe_completo(indicadores, actual, condicion=None, previo=None):
    """Arma UN mensaje con todos los indicadores en formato tabla para Telegram.

    condicion: si se pasa y tiene un nombre, agrega en el Resumen el evento que
    desencadeno el mensaje.
    previo: resultados previos para mostrar la transicion del indicador disparador."""
    W = 38
    barra = None
    precio = None
    for r in actual.values():
        if isinstance(r, dict):
            if "barra" in r and barra is None:
                barra = r["barra"]
            if "precio" in r and precio is None:
                precio = r["precio"]

    lines = []
    lines.append("=" * W)
    header = f"{CONFIG['tv_symbol']} | {CONFIG['timeframe']}"
    lines.append(header.center(W))
    lines.append("=" * W)
    if barra:
        lines.append(f"  Barra    : {barra}")
    if precio:
        lines.append(f"  Precio   : {precio:,.2f} USDT")
    lines.append("")

    # ML RSI
    r = actual.get("ml_rsi")
    if r:
        lines.append("-" * W)
        lines.append("  ML RSI".ljust(W))
        lines.append("-" * W)
        lines.append(f"  RSI actual    : {r['smooth']:.2f}  (RSI {r.get('rsi', r['smooth']):.2f})")
        lines.append(f"  Limite superior: {r['up']:.2f}")
        lines.append(f"  Limite inferior: {r['lo']:.2f}")
        lines.append(f"  Estado         : {r['estado']}")
        lines.append("")

    # RSI 14
    r = actual.get("rsi14")
    if r:
        lines.append("-" * W)
        lines.append("  RSI 14".ljust(W))
        lines.append("-" * W)
        lines.append(f"  RSI 14 actual  : {r['rsi']:.2f}")
        lines.append(f"  Banda superior : {r['up']:.0f}  (distancia {r['diff_up']:.2f})")
        lines.append(f"  Banda inferior : {r['lo']:.0f}  (distancia {r['diff_lo']:.2f})")
        lines.append("")

    # RSI Fractal Energy
    r = actual.get("rsi_fractal")
    if r:
        lines.append("-" * W)
        lines.append("  RSI Fractal Energy".ljust(W))
        lines.append("-" * W)
        lines.append(f"  RSI            : {r.get('rsi', 0):.2f}")
        lines.append(f"  Energy         : {r['energy']:.2f}")
        lines.append(f"  Signal Line    : {r['signal']:.2f}")
        lines.append(f"  Estado         : {r['estado']}")
        lines.append("")

    # ADX
    r = actual.get("adx")
    if r:
        lines.append("-" * W)
        lines.append("  ADX".ljust(W))
        lines.append("-" * W)
        lines.append(f"  ADX            : {r['adx']:.2f}")
        lines.append(f"  DI+            : {r['di_plus']:.2f}")
        lines.append(f"  DI-            : {r['di_minus']:.2f}")
        lines.append(f"  Senal          : {r['estado']}")
        lines.append("")

    # Resumen
    lines.append("=" * W)
    lines.append("  RESUMEN".center(W))
    lines.append("=" * W)
    res_states = (
        ("ML RSI", (actual.get("ml_rsi") or {}).get("estado")),
        ("RSI Fractal", (actual.get("rsi_fractal") or {}).get("estado")),
        ("ADX", (actual.get("adx") or {}).get("estado")),
    )
    for nombre, estado in res_states:
        if estado:
            lines.append(f"  {nombre} : {estado}")
    if condicion and (condicion.get("indicador") or condicion.get("nombre")):
        lines.append("-" * W)
        indicador = condicion.get("indicador")
        campo = condicion.get("campo")
        prev_val = (previo.get(indicador) or {}).get(campo) if indicador and campo and previo else None
        cur_val = (actual.get(indicador) or {}).get(campo) if indicador and campo else None
        if prev_val is not None and cur_val is not None and prev_val != cur_val:
            lines.append(f"  Evento : {prev_val} → {cur_val} ({indicador})")
        else:
            lines.append(f"  Evento : {condicion['nombre']}")
    lines.append("=" * W)

    return "\n".join(lines)


def telegram_informe_completo(indicadores, condicion, actual, previo):
    """Notifica por Telegram un unico mensaje con todos los indicadores juntos."""
    if notify.send_telegram(informe_completo(indicadores, actual, condicion=condicion, previo=previo)):
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
