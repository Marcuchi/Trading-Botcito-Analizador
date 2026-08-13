"""Evaluador de condiciones declarativas definidas en config.CONDICIONES.

Cada condicion trabaja sobre el resultado de un indicador (`campo` dentro del
dict que devuelve `compute`). `actual` y `previo` son diccionarios
indicador -> resultados (este ultimo lo de la ejecucion anterior, persistido).
"""


def _valor(actual, previo, condicion):
    ind = condicion.get("indicador")
    campo = condicion.get("campo")
    if not ind or not campo:
        return None, None
    r = actual.get(ind)
    if not r or campo not in r:
        return None, None
    prev_val = (previo.get(ind, {}) or {}).get(campo) if previo else None
    return r[campo], prev_val


def _cumple_estado(valor, prev_val, condicion):
    """cambio_estado: el valor cambio entre ejecuciones, con filtros opcionales."""
    if prev_val is None or prev_val == valor:
        return False
    desde = condicion.get("desde")
    hacia = condicion.get("hacia")
    if desde is not None and prev_val != desde:
        return False
    if hacia and valor not in hacia:
        return False
    return True


def evaluar(condicion, actual, previo):
    """True si la condicion se cumple con los resultados actuales vs los previos."""
    if not condicion.get("activo", True):
        return False
    tipo = condicion.get("tipo")
    valor, prev_val = _valor(actual, previo, condicion)
    if valor is None:
        return False
    if tipo == "cambio_estado":
        return _cumple_estado(valor, prev_val, condicion)
    if tipo == "mayor_que":
        return valor > condicion.get("valor")
    if tipo == "menor_que":
        return valor < condicion.get("valor")
    if tipo == "igual":
        return valor == condicion.get("valor")
    if tipo == "dentro_de_rango":
        return condicion.get("min") <= valor <= condicion.get("max")
    if tipo == "fuera_de_rango":
        return valor < condicion.get("min") or valor > condicion.get("max")
    raise ValueError(f"tipo de condicion desconocido: {tipo}")
