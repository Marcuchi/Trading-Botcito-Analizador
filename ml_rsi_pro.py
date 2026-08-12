"""ML RSI [BackQuant] | Binance BTC/USDT 1h | Port Python del indicador Pine de BackQuant.

Replica el calculo exacto del indicador "Machine Learning RSI [BackQuant]":
  - RSI(19) de Wilder (ta.rsi).
  - Suavizado opcional con MA configurable (por defecto ALMA(4, sigma=1)).
  - Umbrales dinamicos sobre las ultimas `ml_window` muestras del RSI suavizado:
    p75 (long_S) y p25 (short_S). El K-Means del Pine publicado no altera los
    centroides iniciales en la practica (los valores graficados = p75/p25).
"""

import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from notify import send_telegram

try:
    import pandas_ta as ta
    HAS_TA = True
except ImportError:
    HAS_TA = False

# ------- Parametros estaticos -------
CONFIG = dict(
    symbol="BTC/USDT",
    tv_symbol="BINANCE:BTCUSDT",  # simbolo TradingView usado para el precio spot
    timeframe="1h",
    fetch_limit=10000,
    page=1000,
    rsi_len=19,
    smooth=True,           # suavizar el RSI como en el Pine
    ma_type="ALMA",        # SMA, Hull, Ema, Wma, Dema, RMA, LINREG, TEMA, ALMA, T3
    smooth_len=4,          # Smoothing Period
    alma_sigma=1,          # Sigma for ALMA (solo aplica si ma_type == "ALMA")
    ml_window=3000,        # Max Data Points
    k=3,
    max_iter=1000,         # Max Clustering Steps
    eval_live=True,        # True = barra actual (como Pine), False = ultima cerrada
    sleep_after=3480,
    sleep_retry=60,
    sleep_poll=30,
    telegram_from=None,             # None = alertar ante CUALQUIER transicion de estado
    telegram_to=("Verde", "Gris", "Rojo"),  # estados de destino que disparan la alerta
    telegram_every_run=True,  # enviar el informe completo en cada ejecucion
)

# ------- Colores ANSI -------
GREEN, RED, GRAY, CYAN, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[96m", "\033[0m"

# El Pine define array "factors" con min/max/step del rango de umbrales, pero nunca
# lo usa en el calculo final (codigo muerto del indicador original). No se replica.


# ---------- Extraccion (paginada, Binance limita a 1000/req) ----------
KLINE_API = "https://data-api.binance.vision/api/v3/klines"
TICKER_API = "https://data-api.binance.vision/api/v3/ticker/price"


def fetch_spot_price():
    """Precio spot actual de BINANCE:BTCUSDT (endpoint publico, sin bloqueo regional).
    Devuelve None si falla para no tumbar el analisis."""
    try:
        params = {"symbol": CONFIG["symbol"].replace("/", "")}
        resp = requests.get(TICKER_API, params=params, timeout=15)
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception as e:
        print(f"[WARN] No se pudo obtener el precio spot: {type(e).__name__}: {e}")
        return None


def fetch_ohlcv():
    """Descarga paginada de las ultimas `fetch_limit` velas desde el endpoint de
    mercado publico de Binance (sin bloqueo por region, a diferencia de ccxt)."""
    symbol = CONFIG["symbol"].replace("/", "")
    params = {"symbol": symbol, "interval": CONFIG["timeframe"], "limit": CONFIG["page"]}
    rows, end_time = [], None
    while len(rows) < CONFIG["fetch_limit"]:
        p = dict(params)
        if end_time is not None:
            p["endTime"] = end_time
        resp = requests.get(KLINE_API, params=p, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows[:0] = [k[:6] for k in batch]
        end_time = batch[0][0] - 1
        if len(batch) < CONFIG["page"]:
            break
    rows = rows[-CONFIG["fetch_limit"]:]
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    for col in ("o", "h", "l", "c", "v"):
        df[col] = df[col].astype(float)
    return df


# ---------- Procesamiento matematico ----------
def _rsi_wilder(close, n):
    """RSI de Wilder (RMA), identico al camino no-TA-Lib de pandas_ta / ta.rsi de Pine."""
    d = close.diff()
    a = 1.0 / n
    up = d.clip(lower=0.0).ewm(alpha=a, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=a, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def _ema(series, length):
    """EMA estandar (TradingView/TA-Lib): ewm(span=length), alpha=2/(n+1)."""
    return series.ewm(span=length, adjust=False).mean()


def _wma(series, length):
    """WMA de Pine: el valor mas reciente pesa `length`, el mas antiguo pesa 1."""
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: float(np.dot(x, weights)) / float(weights.sum()), raw=True
    )


def _ma(series, length, ma_type, alma_sigma=1.0):
    """Replica la funcion `ma(src, len, type, sig)` del Pine (10 tipos)."""
    if ma_type == "SMA":
        return series.rolling(length).mean()
    if ma_type == "Hull":
        half = length // 2
        sqrt_len = int(round(length ** 0.5))
        return _wma(2 * _wma(series, half) - _wma(series, length), sqrt_len)
    if ma_type == "Ema":
        return _ema(series, length)
    if ma_type == "Wma":
        return _wma(series, length)
    if ma_type == "Dema":
        e1 = _ema(series, length)
        return 2 * e1 - _ema(e1, length)
    if ma_type == "RMA":
        return series.ewm(alpha=1.0 / length, adjust=False).mean()
    if ma_type == "LINREG":
        idx = np.arange(length)
        def linreg(x):
            slope, intercept = np.polyfit(idx, x, 1)
            return float(slope * (length - 1) + intercept)
        return series.rolling(length).apply(linreg, raw=True)
    if ma_type == "TEMA":
        e1 = _ema(series, length)
        e2 = _ema(e1, length)
        e3 = _ema(e2, length)
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
        e1 = _ema(series, length)
        e2 = _ema(e1, length)
        e3 = _ema(e2, length)
        e4 = _ema(e3, length)
        c1 = -(v ** 3)
        c2 = 3 * (v ** 2) * (1 + v)
        c3 = -3 * v * ((1 + v) ** 2)
        c4 = (1 + v) ** 3
        return c1 * e1 + c2 * e2 + c3 * e3 + c4 * e4
    raise ValueError(f"ma_type desconocido: {ma_type}")


def indicators(df):
    """RSI(19) Wilder + suavizado opcional (ALMA por defecto), igual que el Pine."""
    close = df["c"]
    raw_rsi = ta.rsi(close, length=CONFIG["rsi_len"]) if HAS_TA else _rsi_wilder(close, CONFIG["rsi_len"])
    if CONFIG["smooth"]:
        smooth_rsi = _ma(raw_rsi, CONFIG["smooth_len"], CONFIG["ma_type"], CONFIG["alma_sigma"])
    else:
        smooth_rsi = raw_rsi
    return df.assign(rsi=raw_rsi, smooth=smooth_rsi).dropna(subset=["rsi", "smooth"]).reset_index(drop=True)


def kmeans(x):
    """K-Means 1D (k=3, max 1000 iter). Referencia del algoritmo publicado en el
    Pine; NO se usa en thresholds porque el indicador no altera los centroides
    iniciales en la practica (grafica p75/p25)."""
    x = np.asarray(x, dtype=float)
    c = np.percentile(x, [25.0, 50.0, 75.0])
    for _ in range(CONFIG["max_iter"]):
        lab = np.argmin(np.abs(x[:, None] - c), axis=1)
        nc = c.copy()
        for j in range(CONFIG["k"]):
            g = x[lab == j]
            if g.size:
                nc[j] = g.mean()
        if np.allclose(nc, c):
            c = nc
            break
        c = nc
    return np.sort(c)


def thresholds(w):
    """Umbrales que realmente emite ML RSI [BackQuant]: p75/p25 de la ventana ML.

    El K-Means publicado en Pine no altera los centroides iniciales en la
    practica: los valores graficados por el indicador coinciden con p75/p25
    (verificado empiricamente contra TradingView). """
    return float(np.percentile(w, 75)), float(np.percentile(w, 25))


def classify(r, up, lo):
    return "Verde" if r > up else "Rojo" if r < lo else "Gris"


STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_state.json")


def load_state():
    """Lee el ultimo estado persistido (None si no existe o es ilegible)."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("state")
    except (OSError, ValueError):
        return None


def save_state(state):
    """Persiste el ultimo estado para detectar transiciones entre reinicios."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"state": state}, f)
    except OSError:
        print("[WARN] No se pudo guardar el estado en last_state.json")


def last_closed(df):
    """Descarta la vela en formacion: evalua estrictamente la ultima cerrada."""
    if df["t"].iloc[-1] + pd.Timedelta(hours=1) <= pd.Timestamp.now(tz="UTC"):
        return df
    return df.iloc[:-1].reset_index(drop=True)


def report(row_closed, row_live, up, lo, state, spot=None):
    col = {"Verde": GREEN, "Rojo": RED, "Gris": GRAY}[state]
    bar = "=" * 58
    print(bar)
    print(f"  ML RSI [BQ] | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
    print(bar)
    print(f"  Barra evaluada  : {row_live['t']:%Y-%m-%d %H:%M UTC} (actual)")
    print(f"  Precio actual   : {spot if spot is not None else row_live['c']:,.2f} USDT")
    print(f"  RSI actual      : {row_live['smooth']:.2f}   (RSI {row_live['rsi']:.2f})")
    print(f"  Ultima cerrada  : {row_closed['t']:%Y-%m-%d %H:%M UTC}"
          f" ({row_closed['c']:,.2f} | RSI {row_closed['smooth']:.2f})")
    print(f"  Limite superior : {up:.2f}")
    print(f"  Limite inferior : {lo:.2f}")
    print(f"  Estado          : {col}{state}{RESET}")
    print(bar)


def build_alert_message(state, row, up, lo, header=None, spot=None):
    """Arma el texto del mensaje con los datos del analisis."""
    head = f"{header}\n" if header else ""
    return (
        f"{head}ML RSI [BQ] | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}\n"
        f"Señal: {state.upper()}\n"
        f"Barra: {row['t']:%Y-%m-%d %H:%M UTC}\n"
        f"Precio: {spot if spot is not None else row['c']:,.2f} USDT\n"
        f"RSI suavizado: {row['smooth']:.2f}\n"
        f"Limite superior: {up:.2f}\n"
        f"Limite inferior: {lo:.2f}"
    )


def alert_on_transition(state, row, up, lo, spot=None):
    """Notifica por Telegram ante cualquier cambio de estado (o filtrado por config)."""
    prev = load_state()
    save_state(state)
    if prev is None or prev == state:
        return
    if CONFIG["telegram_from"] is not None and prev != CONFIG["telegram_from"]:
        return
    if state not in CONFIG["telegram_to"]:
        return
    msg = f"{build_alert_message(state, row, up, lo, spot=spot)}\nTransicion: {prev} -> {state}"
    if send_telegram(msg):
        print(f"[TELEGRAM] Alerta de transicion enviada: {prev} -> {state}")


# ---------- Orquestacion ----------
def run_analysis():
    """Replica ML RSI [BackQuant] (Pine): ventana ML y clasificacion sobre la barra actual."""
    df = fetch_ohlcv()
    spot = fetch_spot_price()
    live_open = df["t"].iloc[-1] + pd.Timedelta(hours=1) > pd.Timestamp.now(tz="UTC")
    if spot is not None and CONFIG["eval_live"] and live_open:
        # El cierre de la vela viva del endpoint de klines puede ir desfasado unos
        # segundos; usar el precio spot mas fresco hace que el RSI coincida con TV.
        idx = df.index[-1]
        df.loc[idx, "c"] = spot
        df.loc[idx, "h"] = max(df.loc[idx, "h"], spot)
        df.loc[idx, "l"] = min(df.loc[idx, "l"], spot)
    full = indicators(df)
    if full.empty:
        raise RuntimeError("Sin velas cerradas disponibles.")
    closed = last_closed(full)
    base = full if CONFIG["eval_live"] else closed
    live = base.iloc[-1]
    up, lo = thresholds(base["smooth"].tail(CONFIG["ml_window"]))
    state = classify(live["smooth"], up, lo)
    ref = live if not CONFIG["eval_live"] else closed.iloc[-1]
    report(ref, live, up, lo, state, spot=spot)
    alert_on_transition(state, live, up, lo, spot=spot)
    if CONFIG["telegram_every_run"]:
        msg = build_alert_message(state, live, up, lo, spot=spot)
        if send_telegram(msg):
            print("[TELEGRAM] Informe periodico enviado")
    return state


# ---------- Motor de ejecucion ----------
def engine():
    os.system("")
    done = ()
    print(f"\n{CYAN}ML RSI [BQ] activo | {CONFIG['symbol']} | {CONFIG['timeframe']}{RESET}\n")
    while True:
        now = datetime.now()
        key = (now.year, now.month, now.day, now.hour)
        try:
            if now.minute <= 1 and key != done:
                print(f"{CYAN}[RUN]{RESET} {now:%Y-%m-%d %H:%M:%S} | ultima vela cerrada...")
                run_analysis()
                done = key
                print(f"[INFO] Ok. Durmiendo ~58 min ({CONFIG['sleep_after']}s)\n")
                time.sleep(CONFIG["sleep_after"])
            else:
                time.sleep(CONFIG["sleep_poll"])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(f"[ERROR] {now:%Y-%m-%d %H:%M:%S} | {type(e).__name__}: {e} | Reintento en {CONFIG['sleep_retry']}s\n")
            time.sleep(CONFIG["sleep_retry"])


if __name__ == "__main__":
    try:
        engine()
    except KeyboardInterrupt:
        print("\n[INFO] Motor detenido por el usuario.")
        sys.exit(0)
