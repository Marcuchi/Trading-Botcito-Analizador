"""ML RSI Pro M2M | Binance BTC/USDT 1h | Senal K-Means sobre RSI(14) suavizado con EMA(4)."""

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
    timeframe="1h",
    fetch_limit=10000,
    page=1000,
    rsi_len=14,
    ema_len=4,
    ml_window=3000,
    weight=0.3,
    k=3,
    max_iter=1000,
    eval_live=True,      # True = barra actual (como Pine), False = ultima cerrada
    use_percentile_ml=True,  # True = umbrales p75/p25 (lo que realmente emite el Pine)
    sleep_after=3480,
    sleep_retry=60,
    sleep_poll=30,
    telegram_from="Gris",           # estado de origen que dispara la alerta
    telegram_to=("Verde", "Rojo"),  # estados de destino que disparan la alerta
)

# ------- Colores ANSI -------
GREEN, RED, GRAY, CYAN, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[96m", "\033[0m"


# ---------- Extraccion (paginada, Binance limita a 1000/req) ----------
KLINE_API = "https://data-api.binance.vision/api/v3/klines"


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
    """RSI de Wilder (RMA), identico al camino no-TA-Lib de pandas_ta."""
    d = close.diff()
    a = 1.0 / n
    up = d.clip(lower=0.0).ewm(alpha=a, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=a, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def _ema(series, length):
    """EMA estandar (TradingView/TA-Lib): ewm(span=length), alpha=2/(n+1)."""
    return series.ewm(span=length, adjust=False).mean()


def indicators(df):
    """RSI(14) Wilder + EMA(4) estandar (TradingView). Limpia NaNs."""
    close = df["c"]
    rsi = ta.rsi(close, length=CONFIG["rsi_len"]) if HAS_TA else _rsi_wilder(close, CONFIG["rsi_len"])
    smooth = _ema(rsi, CONFIG["ema_len"])
    return df.assign(rsi=rsi, smooth=smooth).dropna(subset=["rsi", "smooth"]).reset_index(drop=True)


def kmeans(x):
    """K-Means 1D (k=3, max 1000 iter). Centroides iniciales: p25, p50, p75."""
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
    """Umbrales con peso extremo (0.3). Por defecto usa p75/p25, que es lo que
    realmente emite ML RSI Pro (BackQuant) en Pine (el K-Means publicado no
    altera los centroides iniciales). Pasar CONFIG['use_percentile_ml']=False
    activa los centroides convergidos del K-Means."""
    p5, p25, p75, p95 = (np.percentile(w, p) for p in (5, 25, 75, 95))
    wt = CONFIG["weight"]
    if CONFIG["use_percentile_ml"]:
        return p75 * (1 - wt) + p95 * wt, p25 * (1 - wt) + p5 * wt
    c = kmeans(w)
    return c[-1] * (1 - wt) + p95 * wt, c[0] * (1 - wt) + p5 * wt


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


def report(row_closed, row_live, up, lo, state):
    col = {"Verde": GREEN, "Rojo": RED, "Gris": GRAY}[state]
    bar = "=" * 58
    print(bar)
    print(f"  ML RSI Pro | {CONFIG['symbol']} | {CONFIG['timeframe']}")
    print(bar)
    print(f"  Barra evaluada  : {row_live['t']:%Y-%m-%d %H:%M UTC} (actual)")
    print(f"  Precio actual   : {row_live['c']:,.2f} USDT")
    print(f"  RSI actual      : {row_live['smooth']:.2f}   (RSI {row_live['rsi']:.2f})")
    print(f"  Ultima cerrada  : {row_closed['t']:%Y-%m-%d %H:%M UTC}"
          f" ({row_closed['c']:,.2f} | RSI {row_closed['smooth']:.2f})")
    print(f"  Limite superior : {up:.2f}")
    print(f"  Limite inferior : {lo:.2f}")
    print(f"  Estado          : {col}{state}{RESET}")
    print(bar)


def alert_on_transition(state, row):
    """Notifica por Telegram al pasar de CONFIG['telegram_from'] a CONFIG['telegram_to']."""
    prev = load_state()
    save_state(state)
    if state not in CONFIG["telegram_to"] or prev != CONFIG["telegram_from"]:
        return
    msg = (
        f"ML RSI Pro | {CONFIG['symbol']} | {CONFIG['timeframe']}\n"
        f"Señal: {state.upper()}\n"
        f"Transicion: {prev} -> {state}\n"
        f"Barra: {row['t']:%Y-%m-%d %H:%M UTC}\n"
        f"Precio: {row['c']:,.2f} USDT\n"
        f"RSI suavizado: {row['smooth']:.2f}"
    )
    if send_telegram(msg):
        print(f"[TELEGRAM] Alerta enviada: {prev} -> {state}")


# ---------- Orquestacion ----------
def run_analysis():
    """Replica ML RSI Pro (Pine): ventana ML y clasificacion sobre la barra actual."""
    full = indicators(fetch_ohlcv())
    if full.empty:
        raise RuntimeError("Sin velas cerradas disponibles.")
    closed = last_closed(full)
    base = full if CONFIG["eval_live"] else closed
    live = base.iloc[-1]
    up, lo = thresholds(base["smooth"].tail(CONFIG["ml_window"]))
    state = classify(live["smooth"], up, lo)
    ref = live if not CONFIG["eval_live"] else closed.iloc[-1]
    report(ref, live, up, lo, state)
    alert_on_transition(state, live)
    return state


# ---------- Motor de ejecucion ----------
def engine():
    os.system("")
    done = ()
    print(f"\n{CYAN}ML RSI Pro M2M activo | {CONFIG['symbol']} | {CONFIG['timeframe']}{RESET}\n")
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
