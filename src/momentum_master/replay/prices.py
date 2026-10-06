"""Prezzi M1 per il replay: lettura del CSV e "fotografia" del mercato in un istante.

Formato CSV (prodotto da ``replay/export_mt5.py``), una riga per minuto:
    time_utc,open,high,low,close,spread
    2026-09-01T07:00:00+00:00,4480.12,4481.05,4479.80,4480.55,0.25
- prezzi BID (come le barre di MetaTrader 5); ``spread`` in prezzo (spread MT5 × point);
- ``time_utc`` = inizio del minuto, in UTC.

IPOTESI dichiarate (valgono per il replay, non per l'esecuzione dal vivo):
- prezzo alla ricezione di un messaggio = chiusura del minuto che contiene l'istante
  (approssimazione entro 60 s; l'esito si valuta solo dai minuti successivi);
- mercato aperto se esiste una barra negli ultimi 2 minuti;
- inizio/fine della settimana di mercato = prima/ultima barra prima di una pausa > 12 ore.
"""

from __future__ import annotations

import bisect
import csv
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from momentum_master.decision.engine import MarketSnapshot

MINUTE = timedelta(minutes=1)
MARKET_OPEN_TOLERANCE = timedelta(minutes=2)
WEEK_GAP = timedelta(hours=12)


@dataclass(frozen=True)
class Bar:
    time_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    spread: Decimal

    def __post_init__(self) -> None:
        if self.time_utc.tzinfo is None:
            raise ValueError("time_utc deve avere il fuso (UTC)")
        if not (self.low <= min(self.open, self.close) and self.high >= max(self.open, self.close)):
            raise ValueError(f"barra incoerente alle {self.time_utc}")
        if self.spread < 0:
            raise ValueError(f"spread negativo alle {self.time_utc}")


def load_bars_csv(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                bars.append(
                    Bar(
                        datetime.fromisoformat(row["time_utc"]),
                        Decimal(row["open"]),
                        Decimal(row["high"]),
                        Decimal(row["low"]),
                        Decimal(row["close"]),
                        Decimal(row["spread"]),
                    )
                )
            except (KeyError, ValueError, ArithmeticError) as exc:
                raise ValueError(f"{path}:{line_no}: riga non valida: {exc}") from exc
    return bars


class PriceSeries:
    """Serie M1 ordinata, con ricerca per istante e confini delle settimane di mercato."""

    def __init__(self, bars: list[Bar]) -> None:
        if not bars:
            raise ValueError("serie di prezzi vuota")
        self.bars = sorted(bars, key=lambda b: b.time_utc)
        self.times = [b.time_utc for b in self.bars]
        if len(set(self.times)) != len(self.times):
            raise ValueError("barre duplicate nella serie")
        self._week_start: list[datetime] = []
        self._week_end: list[datetime] = []
        start = 0
        for i in range(1, len(self.bars) + 1):
            if i == len(self.bars) or self.times[i] - self.times[i - 1] > WEEK_GAP:
                for _ in range(start, i):
                    self._week_start.append(self.times[start])
                    self._week_end.append(self.times[i - 1] + MINUTE)
                start = i

    def index_at(self, t: datetime) -> int | None:
        """Indice dell'ultima barra iniziata entro ``t`` (None se prima dei dati)."""
        i = bisect.bisect_right(self.times, t) - 1
        return i if i >= 0 else None

    def bars_after(self, t: datetime) -> Iterator[Bar]:
        """Barre che iniziano DOPO il minuto che contiene ``t`` (niente sguardo in avanti)."""
        i = self.index_at(t)
        start = 0 if i is None else i + 1
        yield from self.bars[start:]

    def snapshot(
        self, t: datetime, server_offset_hours: int, stops_level: Decimal
    ) -> MarketSnapshot:
        i = self.index_at(t)
        server_time = (t + timedelta(hours=server_offset_hours)).replace(tzinfo=None)
        if i is None or t - self.times[i] > MARKET_OPEN_TOLERANCE:
            return MarketSnapshot(
                bid=Decimal("0"), ask=Decimal("0"), server_time=server_time,
                trade_allowed=False, stops_level=stops_level,
                minutes_to_week_close=None, minutes_since_week_open=None,
            )  # fmt: skip
        bar = self.bars[i]
        return MarketSnapshot(
            bid=bar.close, ask=bar.close + bar.spread, server_time=server_time,
            trade_allowed=True, stops_level=stops_level,
            minutes_to_week_close=int((self._week_end[i] - t).total_seconds() // 60),
            minutes_since_week_open=int((t - self._week_start[i]).total_seconds() // 60),
        )  # fmt: skip
