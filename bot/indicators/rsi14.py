"""Indicador: RSI 14 - Relative Strength Index (port del RSI nativo de TradingView).

Replica el indicador "Relative Strength Index" de Pine:
  - RSI(14) de Wilder (ta.rma) con bandas 70/50/30 y clasificacion de zona.
  - Suavizado opcional con MA (None, SMA, SMA+Bollinger, EMA, SMMA/RMA, WMA, VWMA).
  - Divergencias regulares alcistas/bajistas (opcional, `calc_divergence`).
"""

import numpy as np

from ..config import CONFIG, hora_cba
from ..data import last_closed
from .base import Indicador
from .ma import ema, wma, vwma, rsi_pine

PARAMS = dict(
    rsi_len=14,
    smooth=True,
    ma_type="SMA",  # None, SMA, SMA + Bollinger Bands, EMA, SMMA (RMA), WMA, VWMA
    ma_length=14,
    bb_mult=2.0,
    calc_divergence=False,
    div_lookback_right=5,
    div_lookback_left=5,
    div_range_upper=60,
    div_range_lower=5,
)

OVERBOUGHT, OVERSOLD = 70.0, 30.0


def _smooth(rsi, volume):
    """Aplica la MA de suavizado del Pine. Devuelve Series o tupla (sma, stdev) para BB."""
    mt, length, mult = PARAMS["ma_type"], PARAMS["ma_length"], PARAMS["bb_mult"]
    if mt in (None, "None"):
        return None
    if mt in ("SMA", "SMA + Bollinger Bands"):
        sma = rsi.rolling(length).mean()
        if mt == "SMA":
            return sma
        stdev = rsi.rolling(length).std(ddof=0) * mult
        return sma, stdev
    if mt == "EMA":
        return ema(rsi, length)
    if mt == "SMMA (RMA)":
        return rsi.ewm(alpha=1.0 / length, adjust=False).mean()
    if mt == "WMA":
        return wma(rsi, length)
    if mt == "VWMA":
        return vwma(rsi, volume, length)
    raise ValueError(f"ma_type desconocido: {mt}")


def _divergence(rsi, high, low):
    """Divergencias regulares del Pine. Recibe arrays numpy y devuelve (bull, bear).

    Replica: pivots (left/right=5), rsi[lookbackRight], valuewhen y barssince.
    """
    left = PARAMS["div_lookback_left"]
    right = PARAMS["div_lookback_right"]
    range_lo = PARAMS["div_range_lower"]
    range_hi = PARAMS["div_range_upper"]
    n = len(rsi)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    is_pl = np.zeros(n, dtype=bool)
    is_ph = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        w = rsi[i - left:i + right + 1]
        if np.isnan(w).any():
            continue
        if rsi[i] <= w.min():
            is_pl[i] = True
        if rsi[i] >= w.max():
            is_ph[i] = True

    prev_pl_rsi = prev_pl_low = prev_pl_t = None
    prev_ph_rsi = prev_ph_high = prev_ph_t = None
    for t in range(right, n):
        if is_pl[t - right]:
            rsi_lbr = rsi[t - right]
            low_lbr = low[t - right]
            if prev_pl_t is not None:
                bars = t - prev_pl_t - 1
                if range_lo <= bars <= range_hi and rsi_lbr > prev_pl_rsi and low_lbr < prev_pl_low:
                    bull[t] = True
            prev_pl_rsi, prev_pl_low, prev_pl_t = rsi_lbr, low_lbr, t
        if is_ph[t - right]:
            rsi_lbr = rsi[t - right]
            high_lbr = high[t - right]
            if prev_ph_t is not None:
                bars = t - prev_ph_t - 1
                if range_lo <= bars <= range_hi and rsi_lbr < prev_ph_rsi and high_lbr > prev_ph_high:
                    bear[t] = True
            prev_ph_rsi, prev_ph_high, prev_ph_t = rsi_lbr, high_lbr, t
    return bull, bear


class RSI14(Indicador):
    nombre = "rsi14"

    def compute(self, df):
        """Calcula RSI(14), suavizado, bandas y divergencias sobre la barra evaluada."""
        full = df.assign(rsi=rsi_pine(df["c"], PARAMS["rsi_len"]))
        smooth = _smooth(full["rsi"], df["v"])
        if isinstance(smooth, tuple):
            sma, stdev = smooth
            full = full.assign(smooth=sma, bb_upper=sma + stdev, bb_lower=sma - stdev)
        elif smooth is not None:
            full = full.assign(smooth=smooth)
        closed = last_closed(full, CONFIG["timeframe"])
        base = full if CONFIG["eval_live"] else closed
        live = base.iloc[-1]
        bull, bear = False, False
        if PARAMS["calc_divergence"]:
            b, k = _divergence(base["rsi"].to_numpy(), base["h"].to_numpy(), base["l"].to_numpy())
            bull, bear = bool(b[-1]), bool(k[-1])
        ref = live if not CONFIG["eval_live"] else closed.iloc[-1]
        r = dict(
            rsi=float(live["rsi"]),
            precio=float(live["c"]),
            barra=live["t"].strftime("%Y-%m-%d %H:%M UTC"),
            up=OVERBOUGHT,
            lo=OVERSOLD,
            ref_barra=ref["t"].strftime("%Y-%m-%d %H:%M UTC"),
            ref_precio=float(ref["c"]),
            ref_rsi=float(ref["rsi"]),
            bull_div=bool(bull),
            bear_div=bool(bear),
        )
        for campo in ("smooth", "bb_upper", "bb_lower"):
            if campo in live:
                r[campo] = float(live[campo])
        return r

    def render(self, resultado):
        r = resultado
        bar = "=" * 58
        print(bar)
        print(f"  RSI 14 | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
        print(bar)
        print(f"  Barra evaluada  : {r['barra']} (actual) ({hora_cba()})")
        print(f"  Precio actual   : {r['precio']:,.2f} USDT")
        suf = f"   (suavizado {r['smooth']:.2f})" if "smooth" in r else ""
        print(f"  RSI 14 actual   : {r['rsi']:.2f}{suf}")
        if "bb_upper" in r:
            print(f"  BB superior     : {r['bb_upper']:.2f}")
            print(f"  BB inferior     : {r['bb_lower']:.2f}")
        print(f"  Ultima cerrada  : {r['ref_barra']} ({r['ref_precio']:,.2f} | RSI {r['ref_rsi']:.2f})")
        print(f"  Bandas          : sup {r['up']:.0f} | inf {r['lo']:.0f}")
        if PARAMS["calc_divergence"]:
            print(f"  Divergencias    : alcista={r['bull_div']} | bajista={r['bear_div']}")
        print(bar)

    def mensaje(self, resultado, header=None):
        r = resultado
        head = f"{header}\n" if header else ""
        lines = [
            f"{head}RSI 14 | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}",
            f"Barra: {r['barra']}",
            f"Precio: {r['precio']:,.2f} USDT",
            f"RSI: {r['rsi']:.2f}",
        ]
        if "smooth" in r:
            lines.append(f"RSI suavizado ({PARAMS['ma_type']}): {r['smooth']:.2f}")
        if "bb_upper" in r:
            lines.append(f"Bandas BB: {r['bb_lower']:.2f} / {r['bb_upper']:.2f}")
        if PARAMS["calc_divergence"]:
            lines.append(f"Divergencia alcista: {r['bull_div']}")
            lines.append(f"Divergencia bajista: {r['bear_div']}")
        return "\n".join(lines)
