"""Registro de indicadores disponibles.

Para agregar un indicador nuevo:
  1) crear bot/indicators/<nombre>.py con la clase heredada de Indicador
  2) registrarlo en REGISTRO
  3) listarlo en INDICADORES (bot/config.py)
"""

from .base import Indicador
from .adx import ADX
from .ml_rsi import MLRSI
from .rsi14 import RSI14
from .rsi_fractal import RSIFractalEnergy

REGISTRO = {
    "ml_rsi": MLRSI,
    "rsi14": RSI14,
    "rsi_fractal": RSIFractalEnergy,
    "adx": ADX,
}


def cargar_indicadores(nombres):
    """Instancia los indicadores pedidos por nombre (lista de config.INDICADORES)."""
    desconocidos = set(nombres) - set(REGISTRO)
    if desconocidos:
        raise ValueError(f"Indicador(es) no registrado(s): {sorted(desconocidos)}")
    return {nombre: REGISTRO[nombre]() for nombre in nombres}
