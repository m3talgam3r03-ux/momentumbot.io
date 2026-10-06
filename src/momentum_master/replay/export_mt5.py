"""Esportazione dei prezzi M1 da MetaTrader 5 in CSV per il replay (solo Windows).

Uso (con il terminale MT5 di FPG aperto e collegato al conto, anche DEMO):
    python -m momentum_master.replay.export_mt5 --simbolo XAUUSD --dal 2026-08-25 --al 2026-10-07 \\
        --out data/xauusd_m1.csv

Funzioni MetaTrader5 usate (verificate nel pacchetto 5.0.6231): initialize, symbol_select,
symbol_info, symbol_info_tick, copy_rates_range, TIMEFRAME_M1, last_error, shutdown.

IPOTESI (da verificare al primo uso, il comando stampa i dati per controllarle):
- il campo ``time`` delle barre è l'ora del SERVER espressa come secondi dal 1970;
- lo scarto server−UTC si stima dall'ultimo tick (a mercato aperto) arrotondato all'ora,
  oppure si passa a mano con --offset-server;
- le barre disponibili dipendono da "Strumenti → Opzioni → Grafici → Barre max nel grafico":
  6 settimane di M1 sono circa 60.000 barre.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any


def estimate_server_offset_hours(tick_time_server: int, now_utc: float) -> int:
    """Scarto server−UTC in ore, dall'ultimo tick (valido solo se il tick è recente)."""
    return round((tick_time_server - now_utc) / 3600)


def rates_to_rows(
    rates: Iterable[Mapping[str, Any]], point: float, digits: int, offset_hours: int
) -> list[dict[str, str]]:
    """Converte le barre MT5 in righe CSV: ora in UTC, prezzi e spread in prezzo."""
    quant = Decimal(1).scaleb(-digits)
    pt = Decimal(str(point))
    rows = []
    for r in rates:
        server = datetime.fromtimestamp(int(r["time"]), UTC)
        utc = server - timedelta(hours=offset_hours)

        def price(key: str, _r: Mapping[str, Any] = r) -> str:
            return str(Decimal(str(_r[key])).quantize(quant))

        rows.append({
            "time_utc": utc.isoformat(),
            "open": price("open"), "high": price("high"), "low": price("low"),
            "close": price("close"),
            "spread": str((Decimal(int(r["spread"])) * pt).quantize(quant)),
        })  # fmt: skip
    return rows


def write_csv(rows: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_utc", "open", "high", "low", "close",
                                                    "spread"])  # fmt: skip
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.replay.export_mt5")
    parser.add_argument("--simbolo", required=True, help="nome esatto sul conto, es. XAUUSD-e")
    parser.add_argument("--dal", required=True, help="AAAA-MM-GG (UTC)")
    parser.add_argument("--al", required=True, help="AAAA-MM-GG (UTC, escluso)")
    parser.add_argument("--out", default="data/xauusd_m1.csv")
    parser.add_argument("--terminale", default=None, help="percorso di terminal64.exe")
    parser.add_argument("--offset-server", type=int, default=None, help="ore server−UTC")
    args = parser.parse_args(argv)

    try:
        import MetaTrader5 as mt5  # type: ignore[import-not-found]
    except ImportError:
        print("Libreria MetaTrader5 non installata: pip install -r requirements-windows.txt")
        return 2

    ok = mt5.initialize(path=args.terminale) if args.terminale else mt5.initialize()
    if not ok:
        print(f"MT5 non inizializzato: {mt5.last_error()}")
        return 1
    try:
        if not mt5.symbol_select(args.simbolo, True):
            print(f"Simbolo {args.simbolo} non trovato: {mt5.last_error()}")
            return 1
        info = mt5.symbol_info(args.simbolo)
        tick = mt5.symbol_info_tick(args.simbolo)
        offset = args.offset_server
        if offset is None:
            offset = estimate_server_offset_hours(int(tick.time), time.time())
        print(f"{args.simbolo}: point {info.point}, digits {info.digits}, "
              f"scarto server−UTC stimato {offset} h (ultimo tick {tick.time})")  # fmt: skip
        start = datetime.fromisoformat(args.dal).replace(tzinfo=UTC) - timedelta(days=1)
        end = datetime.fromisoformat(args.al).replace(tzinfo=UTC) + timedelta(days=1)
        rates = mt5.copy_rates_range(args.simbolo, mt5.TIMEFRAME_M1, start, end)
        if rates is None or len(rates) == 0:
            print(f"Nessuna barra: {mt5.last_error()} (controlla 'Barre max nel grafico')")
            return 1
        rows = rates_to_rows(rates, info.point, info.digits, offset)
        lo = datetime.fromisoformat(args.dal).replace(tzinfo=UTC)
        hi = datetime.fromisoformat(args.al).replace(tzinfo=UTC)
        rows = [r for r in rows if lo <= datetime.fromisoformat(r["time_utc"]) < hi]
        write_csv(rows, Path(args.out))
        print(f"{len(rows)} barre M1 → {args.out} (prima {rows[0]['time_utc']}, "
              f"ultima {rows[-1]['time_utc']})")  # fmt: skip
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
