"""Indicador: RSI Fractal Energy con Signal Line (port del Pine de Cookie1245).

Replica "RSI Fractal Energy with Signal Line":
  - RSI(14) sobre close.
  - Fractales (ta.highest/ta.lowest) con longitud configurable.
  - energy = abs(RSI - 50) * 2.
  - signal_line = SMA(energy, signal_period).

El mensaje acoplado clasifica el momento segun energia:
  - "Movimiento con Energia": energy >= 40 y energy > signal_line.
  - "Sin Energia": la barra previa tenia energy >= signal_line y ahora energy < signal_line.
  - "Neutro": ninguno de los dos casos.
"""

from ..config import CONFIG, GREEN, RED, GRAY, RESET
from ..data import last_closed
from .base import Indicador
from .ma import rsi_pine

PARAMS = dict(
    rsi_len=14,
    fractal_len=5,
    signal_period=9,
)

MIN_ENERGY = 40.0


class RSIFractalEnergy(Indicador):
    nombre = "rsi_fractal"

    def compute(self, df):
        rsi = rsi_pine(df["c"], PARAMS["rsi_len"])
        energy = (rsi - 50).abs() * 2
        signal_line = energy.rolling(PARAMS["signal_period"]).mean()
        full = df.assign(rsi=rsi, energy=energy, signal=signal_line).dropna(
            subset=["rsi", "energy", "signal"]
        ).reset_index(drop=True)
        if full.empty:
            raise RuntimeError("Sin velas cerradas disponibles.")
        closed = last_closed(full, CONFIG["timeframe"])
        base = full if CONFIG["eval_live"] else closed
        live = base.iloc[-1]
        prev = base.iloc[-2] if len(base) > 1 else live
        energy = float(live["energy"])
        signal = float(live["signal"])
        p_energy = float(prev["energy"])
        p_signal = float(prev["signal"])
        return dict(
            estado=self._estado(energy, signal, p_energy, p_signal),
            energy=energy,
            signal=signal,
            prev_energy=p_energy,
            prev_signal=p_signal,
            rsi=float(live["rsi"]),
            barra=live["t"].strftime("%Y-%m-%d %H:%M UTC"),
        )

    @staticmethod
    def _estado(energy, signal, p_energy, p_signal):
        if energy >= MIN_ENERGY and energy > signal:
            return "Movimiento con Energia"
        if p_energy >= p_signal and energy < signal:
            return "Sin Energia"
        return "Neutro"

    def render(self, resultado):
        r = resultado
        col = {"Movimiento con Energia": GREEN, "Sin Energia": RED, "Neutro": GRAY}[r["estado"]]
        bar = "=" * 58
        print(bar)
        print(f"  RSI Fractal Energy | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}")
        print(bar)
        print(f"  Barra evaluada  : {r['barra']}")
        print(f"  RSI             : {r['rsi']:.2f}")
        print(f"  Energy          : {r['energy']:.2f}")
        print(f"  Signal Line     : {r['signal']:.2f}")
        print(f"  Energy previa   : {r['prev_energy']:.2f}")
        print(f"  Signal previa   : {r['prev_signal']:.2f}")
        print(f"  Estado          : {col}{r['estado']}{RESET}")
        print(bar)

    def mensaje(self, resultado, header=None):
        r = resultado
        head = f"{header}\n" if header else ""
        return (
            f"{head}RSI Fractal Energy | {CONFIG['tv_symbol']} | {CONFIG['timeframe']}\n"
            f"Barra: {r['barra']}\n"
            f"Energy: {r['energy']:.2f}\n"
            f"Signal Line: {r['signal']:.2f}\n"
            f"Estado: {r['estado']}"
        )
