"""Capa de datos: descarga de velas y precio spot desde Binance.

Endpoints publicos de mercado que no sufren bloqueo por region (a diferencia de ccxt).
"""

import pandas as pd
import requests

KLINE_API = "https://data-api.binance.vision/api/v3/klines"
TICKER_API = "https://data-api.binance.vision/api/v3/ticker/price"


def tf_to_timedelta(timeframe):
    """Convierte un timeframe de TradingView ("1h", "5m", "1d") a pd.Timedelta."""
    value = int(timeframe[:-1])
    unit = timeframe[-1]
    if unit == "m":
        return pd.Timedelta(minutes=value)
    if unit == "h":
        return pd.Timedelta(hours=value)
    if unit == "d":
        return pd.Timedelta(days=value)
    raise ValueError(f"timeframe no soportado: {timeframe}")


def fetch_spot_price(config):
    """Precio spot actual (endpoint publico). Devuelve None si falla para no tumbar el analisis."""
    try:
        params = {"symbol": config["symbol"].replace("/", "")}
        resp = requests.get(TICKER_API, params=params, timeout=15)
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception as e:
        print(f"[WARN] No se pudo obtener el precio spot: {type(e).__name__}: {e}")
        return None


def fetch_ohlcv(config):
    """Descarga paginada de las ultimas `fetch_limit` velas (Binance limita a 1000/req)."""
    symbol = config["symbol"].replace("/", "")
    params = {"symbol": symbol, "interval": config["timeframe"], "limit": config["page"]}
    rows, end_time = [], None
    while len(rows) < config["fetch_limit"]:
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
        if len(batch) < config["page"]:
            break
    rows = rows[-config["fetch_limit"]:]
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    for col in ("o", "h", "l", "c", "v"):
        df[col] = df[col].astype(float)
    return df


def last_closed(df, timeframe="1h"):
    """Descarta la vela en formacion: evalua estrictamente la ultima cerrada."""
    if df["t"].iloc[-1] + tf_to_timedelta(timeframe) <= pd.Timestamp.now(tz="UTC"):
        return df
    return df.iloc[:-1].reset_index(drop=True)


def preparar_datos(config):
    """Descarga las velas y, si la barra actual sigue abierta, le inyecta el precio
    spot mas fresco para que los indicadores coincidan con TradingView."""
    df = fetch_ohlcv(config)
    spot = fetch_spot_price(config)
    live_open = df["t"].iloc[-1] + tf_to_timedelta(config["timeframe"]) > pd.Timestamp.now(tz="UTC")
    if spot is not None and config["eval_live"] and live_open:
        idx = df.index[-1]
        df.loc[idx, "c"] = spot
        df.loc[idx, "h"] = max(df.loc[idx, "h"], spot)
        df.loc[idx, "l"] = min(df.loc[idx, "l"], spot)
    return df
