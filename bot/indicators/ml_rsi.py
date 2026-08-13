"""Indicador: ML RSI [BackQuant] | Binance BTC/USDT | Port Python del Pine.

Replica el calculo exacto del indicador "Machine Learning RSI [BackQuant]":
  - RSI(19) de Wilder (ta.rsi).
  - Suavizado opcional con MA configurable (por defecto ALMA(4, sigma=1)).
  - Umbrales dinamicos sobre las ultimas `ml_window` muestras del RSI suavizado:
    p75 (long_S) y p25 (short_S). El K-Means del Pine publicado no altera los
    centroides iniciales en la practica (los valores graficados = p75/p25).
"""

import numpy as np
import pandas as pd

from ..config import CONFIG, GREEN, RED, GRAY, RESET, hora_cba
from ..data import last_closed
from .base import Indicador
from .ma import rsi as calc_rsi, ma as calc_ma

PARAMS = dict(
    rsi_len=19,
    smooth=True,           # suavizar el RSI como en el Pine
    ma_type="ALMA",        # SMA, Hull, Ema, Wma, Dema, RMA, LINREG, TEMA, ALMA, T3
    smooth_len=4,          # Smoothing Period
    alma_sigma=1,          # Sigma for ALMA (solo aplica si ma_type == "ALMA")
    ml_window=3000,        # Max Data Points
    k=3,
    max_iter=1000,         # Max Clustering Steps
)


def thresholds(w):
    """Umbrales que realmente emite ML RSI [BackQuant]: p75/p25 de la ventana ML."""
    return float(np.percentile(w, 75)), float(np.percentile(w, 25))


def classify(r, up, lo):
    """Clasifica el RSI suavizado en Verde / Gris / Rojo segun los umbrales."""
    return "Verde" if r > up else "Rojo" if r < lo else "Gris"


class MLRSI(Indicador):
    nombre = "ml_rsi"

    def compute(self, df):
        """Calcula RSI suavizado, umbrales y estado sobre la barra evaluada.

        Devuelve un dict serializable con los resultados del indicador.
        """
        close = df["c"]
        raw_rsi = calc_rsi(close, PARAMS["rsi_len"])
        if PARAMS["smooth"]:
            smooth = calc_ma(raw_rsi, PARAMS["smooth_len"], PARAMS["ma_type"], PARAMS["alma_sigma"])
        else:
            smooth = raw_rsi
        full = df.assign(rsi=raw_rsi, smooth=smooth).dropna(subset=["rsi", "smooth"]).reset_index(drop=True)
        if full.empty:
            raise RuntimeError("Sin velas cerradas disponibles.")
        closed = last_closed(full, CONFIG["timeframe"])
        base = full if CONFIG["eval_live"] else closed
        live = base.iloc[-1]
        up, lo = thresholds(base["smooth"].tail(PARAMS["ml_window"]))
        estado = classify(live["smooth"], up, lo)
        ref = live if not CONFIG["eval_live"] else closed.iloc[-1]
        return dict(
            estado=estado,
            rsi=float(live["rsi"]),
            smooth=float(live["smooth"]),
            precio=float(live["c"]),
            barra=live["t"].strftime("%Y-%m-%d %H:%M UTC"),
            up=up,
            lo=lo,
            ref_barra=ref["t"].strftime("%Y-%m-%d %H:%M UTC"),
            ref_precio=float(ref["c"]),
            ref_smooth=float(ref["smooth"]),
        )

    def render(self, resultado):
        r = resultado
        col = {"Verde": GREEN, "Rojo": RED, "Gris": GRAY}[r["estado"]]
        bar = "=" * 58
        print(bar)
        print(f"  ML RSI [BQ] | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
        print(bar)
        print(f"  Barra evaluada  : {r['barra']} (actual) ({hora_cba()})")
        print(f"  Precio actual   : {r['precio']:,.2f} USDT")
        print(f"  RSI actual      : {r['smooth']:.2f}   (RSI {r['rsi']:.2f})")
        print(f"  Ultima cerrada  : {r['ref_barra']} ({r['ref_precio']:,.2f} | RSI {r['ref_smooth']:.2f})")
        print(f"  Limite superior : {r['up']:.2f}")
        print(f"  Limite inferior : {r['lo']:.2f}")
        print(f"  Estado          : {col}{r['estado']}{RESET}")
        print(bar)

    def mensaje(self, resultado, header=None):
        r = resultado
        head = f"{header}\n" if header else ""
        return (
            f"{head}ML RSI [BQ] | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}\n"
            f"Señal: {r['estado'].upper()}\n"
            f"Barra: {r['barra']}\n"
            f"Precio: {r['precio']:,.2f} USDT\n"
            f"RSI suavizado: {r['smooth']:.2f}\n"
            f"Limite superior: {r['up']:.2f}\n"
            f"Limite inferior: {r['lo']:.2f}"
        )
