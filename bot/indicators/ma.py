"""Utilidades matematicas compartidas por los indicadores: RSI de Wilder y medias moviles.

Las funciones de media replican la funcion `ma(src, len, type, sig)` del Pine
(10 tipos) y se usan tanto para el suavizado de indicadores como por otros
indicadores que lo necesiten.
"""

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta

    HAS_TA = True
except ImportError:
    HAS_TA = False


def rsi_wilder(close, n):
    """RSI de Wilder (RMA), identico al camino no-TA-Lib de pandas_ta / ta.rsi de Pine."""
    d = close.diff()
    a = 1.0 / n
    up = d.clip(lower=0.0).ewm(alpha=a, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=a, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def rsi(close, n):
    """RSI usando pandas_ta si esta instalado, con fallback nativo identico."""
    if HAS_TA:
        return ta.rsi(close, length=n)
    return rsi_wilder(close, n)


def rsi_pine(close, n):
    """RSI exacto del Pine nativo (ta.rma) con sus casos borde: down==0 -> 100, up==0 -> 0."""
    d = close.diff()
    a = 1.0 / n
    up = d.clip(lower=0.0).ewm(alpha=a, adjust=False, min_periods=n).mean().to_numpy()
    down = (-d.clip(upper=0.0)).ewm(alpha=a, adjust=False, min_periods=n).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        val = np.where(down == 0, 100.0, np.where(up == 0, 0.0, 100 - 100 / (1 + up / down)))
    return pd.Series(val, index=close.index)


def vwma(series, volume, length):
    """VWMA de Pine: sum(src*vol) / sum(vol) en la ventana."""
    return (series * volume).rolling(length).sum() / volume.rolling(length).sum()


def ema(series, length):
    """EMA estandar (TradingView/TA-Lib): ewm(span=length), alpha=2/(n+1)."""
    return series.ewm(span=length, adjust=False).mean()


def wma(series, length):
    """WMA de Pine: el valor mas reciente pesa `length`, el mas antiguo pesa 1."""
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: float(np.dot(x, weights)) / float(weights.sum()), raw=True
    )


def ma(series, length, ma_type, alma_sigma=1.0):
    """Replica la funcion `ma(src, len, type, sig)` del Pine (10 tipos)."""
    if ma_type == "SMA":
        return series.rolling(length).mean()
    if ma_type == "Hull":
        half = length // 2
        sqrt_len = int(round(length ** 0.5))
        return wma(2 * wma(series, half) - wma(series, length), sqrt_len)
    if ma_type == "Ema":
        return ema(series, length)
    if ma_type == "Wma":
        return wma(series, length)
    if ma_type == "Dema":
        e1 = ema(series, length)
        return 2 * e1 - ema(e1, length)
    if ma_type == "RMA":
        return series.ewm(alpha=1.0 / length, adjust=False).mean()
    if ma_type == "LINREG":
        idx = np.arange(length)

        def linreg(x):
            slope, intercept = np.polyfit(idx, x, 1)
            return float(slope * (length - 1) + intercept)

        return series.rolling(length).apply(linreg, raw=True)
    if ma_type == "TEMA":
        e1 = ema(series, length)
        e2 = ema(e1, length)
        e3 = ema(e2, length)
        return 3 * e1 - 3 * e2 + e3
    if ma_type == "ALMA":
        offset = 0.0  # el Pine pasa offset=0
        m = int(offset * (length - 1))
        s = length / alma_sigma
        weights = np.exp(-((np.arange(length) - m) ** 2) / (2 * s * s))
        weights /= weights.sum()
        # ta.alma de Pine: sum += series[windowsize - i - 1] * w[i], o sea w[0]
        # (el mayor) se aplica al valor MAS ANTIGUO y w[n-1] al actual.
        def alma(x):
            return float(np.dot(weights, x))

        return series.rolling(length).apply(alma, raw=True)
    if ma_type == "T3":
        v = 0.7  # el Pine usa 0.7 fijo
        e1 = ema(series, length)
        e2 = ema(e1, length)
        e3 = ema(e2, length)
        e4 = ema(e3, length)
        c1 = -(v ** 3)
        c2 = 3 * (v ** 2) * (1 + v)
        c3 = -3 * v * ((1 + v) ** 2)
        c4 = (1 + v) ** 3
        return c1 * e1 + c2 * e2 + c3 * e3 + c4 * e4
    raise ValueError(f"ma_type desconocido: {ma_type}")


def kmeans_1d(x, k=3, max_iter=1000):
    """K-Means 1D del Pine publicado (k=3, max 1000 iter). Referencia: el indicador
    no altera los centroides iniciales en la practica (grafica p75/p25)."""
    x = np.asarray(x, dtype=float)
    c = np.percentile(x, [25.0, 50.0, 75.0])
    for _ in range(max_iter):
        lab = np.argmin(np.abs(x[:, None] - c), axis=1)
        nc = c.copy()
        for j in range(k):
            g = x[lab == j]
            if g.size:
                nc[j] = g.mean()
        if np.allclose(nc, c):
            c = nc
            break
        c = nc
    return np.sort(c)
