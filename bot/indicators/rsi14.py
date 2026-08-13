"""Indicador: RSI 14 - Relative Strength Index (port del RSI nativo de TradingView).

Replica el indicador "Relative Strength Index" de Pine:
  - RSI(14) de Wilder (ta.rma) con bandas 70/30.
  - Distancia en valor absoluto del RSI actual a cada banda.
"""

import numpy as np

from ..config import CONFIG
from ..data import last_closed
from .base import Indicador
from .ma import rsi_pine

PARAMS = dict(
    rsi_len=14,
)

OVERBOUGHT, OVERSOLD = 70.0, 30.0


class RSI14(Indicador):
    nombre = "rsi14"

    def compute(self, df):
        """Calcula RSI(14) y las distancias absolutas a las bandas 70/30."""
        full = df.assign(rsi=rsi_pine(df["c"], PARAMS["rsi_len"]))
        closed = last_closed(full, CONFIG["timeframe"])
        base = full if CONFIG["eval_live"] else closed
        live = base.iloc[-1]
        rsi = float(live["rsi"])
        return dict(
            rsi=rsi,
            up=OVERBOUGHT,
            lo=OVERSOLD,
            diff_up=abs(rsi - OVERBOUGHT),
            diff_lo=abs(rsi - OVERSOLD),
        )

    def render(self, resultado):
        r = resultado
        bar = "=" * 58
        print(bar)
        print(f"  RSI 14 | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
        print(bar)
        print(f"  RSI 14 actual  : {r['rsi']:.2f}")
        print(f"  Banda superior : {r['up']:.0f}  (distancia {r['diff_up']:.2f})")
        print(f"  Banda inferior : {r['lo']:.0f}  (distancia {r['diff_lo']:.2f})")
        print(bar)

    def mensaje(self, resultado, header=None):
        r = resultado
        head = f"{header}\n" if header else ""
        return (
            f"{head}RSI 14 | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}\n"
            f"RSI: {r['rsi']:.2f}\n"
            f"Banda superior ({r['up']:.0f}): distancia {r['diff_up']:.2f}\n"
            f"Banda inferior ({r['lo']:.0f}): distancia {r['diff_lo']:.2f}"
        )
