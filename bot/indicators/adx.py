"""Indicador: ADX - Average Directional Index (port del Pine nativo de TradingView).

Replica "Average Directional Index":
  - dirmov(len): DI+ y DI- usando RMA sobre true range, DM+ y DM-.
  - adx(dilen, adxlen): 100 * RMA(abs(DI+ - DI-) / (sum || 1), adxlen).

El mensaje asociado clasifica la fuerza de la tendencia:
  - ADX < 25  (Ruido): "No entrar".
  - ADX 25-50 (Fase Optima): "Ejecutar Entrada".
  - ADX > 50  (Sobreextension): "Alta volatilidad, Posible regresion, Stop Loss/ Salir".
"""

from ..config import CONFIG, GREEN, RED, GRAY, RESET
from ..data import last_closed
from .base import Indicador

PARAMS = dict(
    adx_len=14,
    di_len=14,
)

import numpy as np
import pandas as pd


def rma(series, length):
    """RMA de Pine: ewm(alpha=1/length, adjust=False)."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()


def true_range(df):
    """True Range de Pine: max(high-low, |high-prev_close|, |low-prev_close|)."""
    prev_close = df["c"].shift(1)
    tr = pd.concat(
        [
            df["h"] - df["l"],
            (df["h"] - prev_close).abs(),
            (df["l"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def dirmov(df, length):
    """DI+ y DI- de Pine (dirmov)."""
    up = df["h"].diff()
    down = -df["l"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    truerange = rma(true_range(df), length)
    plus = 100.0 * rma(plus_dm, length) / truerange
    minus = 100.0 * rma(minus_dm, length) / truerange
    return plus, minus


class ADX(Indicador):
    nombre = "adx"

    def compute(self, df):
        plus, minus = dirmov(df, PARAMS["di_len"])
        suma = plus + minus
        suma_guardada = suma.replace(0, 1.0)
        adx_series = 100.0 * rma((plus - minus).abs() / suma_guardada, PARAMS["adx_len"])
        full = df.assign(adx=adx_series, di_plus=plus, di_minus=minus).dropna(
            subset=["adx", "di_plus", "di_minus"]
        ).reset_index(drop=True)
        if full.empty:
            raise RuntimeError("Sin velas cerradas disponibles.")
        closed = last_closed(full, CONFIG["timeframe"])
        base = full if CONFIG["eval_live"] else closed
        live = base.iloc[-1]
        adx = float(live["adx"])
        return dict(
            adx=adx,
            di_plus=float(live["di_plus"]),
            di_minus=float(live["di_minus"]),
            estado=self._estado(adx),
            barra=live["t"].strftime("%Y-%m-%d %H:%M UTC"),
        )

    @staticmethod
    def _estado(adx):
        if adx > 50.0:
            return "Alta volatilidad, Posible regresion, Stop Loss/ Salir"
        if adx >= 25.0:
            return "Ejecutar Entrada"
        return "No entrar"

    def render(self, resultado):
        r = resultado
        if r["adx"] < 25.0:
            col = RED
        elif r["adx"] <= 50.0:
            col = GREEN
        else:
            col = GRAY
        bar = "=" * 58
        print(bar)
        print(f"  ADX | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
        print(bar)
        print(f"  Barra evaluada  : {r['barra']}")
        print(f"  ADX             : {r['adx']:.2f}")
        print(f"  DI+             : {r['di_plus']:.2f}")
        print(f"  DI-             : {r['di_minus']:.2f}")
        print(f"  Señal           : {col}{r['estado']}{RESET}")
        print(bar)

    def mensaje(self, resultado, header=None):
        r = resultado
        head = f"{header}\n" if header else ""
        return (
            f"{head}ADX | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}\n"
            f"Barra: {r['barra']}\n"
            f"ADX: {r['adx']:.2f}\n"
            f"DI+: {r['di_plus']:.2f} | DI-: {r['di_minus']:.2f}\n"
            f"Señal: {r['estado']}"
        )
