"""Replay: lo storico del canale passa dalla STESSA pipeline del bot dal vivo, con i prezzi M1.

Per ogni messaggio, in ordine di tempo:
1. mercato = fotografia M1 all'istante di ricezione (pubblicazione + latenza);
2. classifica → collega → decide (S1-S11, filtri del config, doppioni, D2…);
3. apertura approvata → simulazione dell'esito; CANCEL/CLOSE del fornitore → l'operazione
   collegata viene troncata in quell'istante.
Il limite F11 sulle posizioni aperte usa le operazioni simulate ancora attive.

Uso:
    python -m momentum_master.replay --storico data/storico.jsonl --prezzi data/xauusd_m1.csv \\
        --offset-server 3 --out data/replay.md
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from momentum_master.config import AppConfig, ConfigError, load_config
from momentum_master.decision.engine import Action, Decision, MessageContext
from momentum_master.exporter.export import read_jsonl
from momentum_master.exporter.models import ExportedMessage
from momentum_master.pipeline import process_message
from momentum_master.replay.prices import PriceSeries, load_bars_csv
from momentum_master.replay.simulate import Outcome, TradeResult, TradeSpec, simulate
from momentum_master.store import Store


@dataclass
class ReplayResult:
    trades: dict[int, TradeResult] = field(default_factory=dict)
    decisions: Counter[tuple[str, str]] = field(default_factory=Counter)
    first: str = ""
    last: str = ""

    def closed(self) -> list[TradeResult]:
        done = [t for t in self.trades.values() if t.is_closed]
        return sorted(done, key=lambda t: (t.exit_at, t.spec.signal_msg_id))


def run_replay(
    messages: Iterable[ExportedMessage],
    series: PriceSeries,
    cfg: AppConfig,
    *,
    server_offset_hours: int,
    stops_level: Decimal = Decimal("0"),
    latency: timedelta = timedelta(seconds=1),
) -> ReplayResult:
    store = Store(":memory:")
    result = ReplayResult()
    ordered = sorted(messages, key=lambda m: (m.date_utc, m.msg_id))
    if ordered:
        result.first, result.last = (
            f"{ordered[0].date_utc:%d/%m/%Y}",
            f"{ordered[-1].date_utc:%d/%m/%Y}",
        )
    for msg in ordered:
        t = msg.date_utc + latency
        active = sum(trade.active_at(t) for trade in result.trades.values())
        snapshot = series.snapshot(t, server_offset_hours, stops_level)
        decision: Decision = process_message(
            msg, MessageContext(received_at_utc=t, is_forward=msg.is_forward), snapshot, cfg,
            store, open_positions=active,
        )  # fmt: skip
        result.decisions[(decision.action.value, decision.reason.value)] += 1
        if decision.is_open:
            spec = TradeSpec(
                signal_msg_id=msg.msg_id, side=decision.side,  # type: ignore[arg-type]
                order_type=decision.order_type or "MARKET",
                entry=decision.entry_price, sl=decision.sl, tp=decision.tp,  # type: ignore[arg-type]
                decided_at=t, expiry=decision.expiry_utc,
            )  # fmt: skip
            result.trades[msg.msg_id] = simulate(spec, series)
        elif decision.action in (Action.CANCEL, Action.CLOSE):
            target = decision.target_msg_id
            if target in result.trades and result.trades[target].active_at(t):
                result.trades[target] = simulate(result.trades[target].spec, series, cutoff=t)
    store.close()
    return result


def _max_drawdown(rs: list[Decimal]) -> Decimal:
    equity = peak = worst = Decimal("0")
    for r in rs:
        equity += r
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def build_report(result: ReplayResult, cfg: AppConfig, title: str = "Replay") -> str:
    closed = result.closed()
    outcomes = Counter(t.outcome for t in result.trades.values())
    rs = [t.r for t in closed if t.r is not None]
    be = "spento" if cfg.targets.be_after_tp is None else f"dopo TP{cfg.targets.be_after_tp}"
    lines = [
        f"# {title}",
        "",
        f"Periodo dei messaggi: {result.first} → {result.last}. Config {cfg.meta.version}, "
        f"TP{cfg.targets.tp_index}, BE {be}.",
        "",
        "> Simulazione su prezzi M1 con ipotesi prudenti (vedi `replay/simulate.py`). "
        "Non è una previsione di risultati futuri né un consiglio di investimento.",
        "",
        "## Operazioni",
        "",
        "| Esito | Numero |",
        "|---|---|",
    ]
    lines += [f"| {o.value} | {outcomes.get(o, 0)} |" for o in Outcome]
    if rs:
        wins = sum(1 for r in rs if r > 0)
        total = sum(rs)
        lines += [
            "",
            "| Misura | Valore |",
            "|---|---|",
            f"| Operazioni chiuse | {len(rs)} |",
            f"| Win rate (R > 0) | {wins / len(rs):.1%} |",
            f"| Risultato totale | {total:+.2f} R |",
            f"| Aspettativa | {total / len(rs):+.3f} R per operazione |",
            f"| Drawdown massimo | {_max_drawdown(rs):.2f} R |",
            f"| Punti totali | {sum(t.points for t in closed if t.points is not None):+.2f} |",
        ]
        weeks: Counter[str] = Counter()
        count: Counter[str] = Counter()
        for t in closed:
            key = f"{t.exit_at:%G-W%V}"
            weeks[key] += float(t.r or 0)
            count[key] += 1
        lines += ["", "## Per settimana", "", "| Settimana | Operazioni | R |", "|---|---|---|"]
        lines += [f"| {w} | {count[w]} | {weeks[w]:+.2f} |" for w in sorted(weeks)]
    lines += ["", "## Decisioni", "", "| Azione | Motivo | Numero |", "|---|---|---|"]
    lines += [f"| {a} | {r} | {n} |" for (a, r), n in result.decisions.most_common()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.replay")
    parser.add_argument("--storico", required=True, help="JSONL dei messaggi")
    parser.add_argument("--prezzi", required=True, help="CSV M1 (replay/export_mt5.py)")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--offset-server", type=int, required=True,
                        help="ore tra ora del server MT5 e UTC (es. 3)")  # fmt: skip
    parser.add_argument("--stops-level", default="0", help="trade_stops_level × point, in prezzo")
    parser.add_argument("--out", default="data/replay.md")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as exc:
        print(exc)
        return 1
    series = PriceSeries(load_bars_csv(Path(args.prezzi)))
    result = run_replay(
        read_jsonl(Path(args.storico)), series, cfg,
        server_offset_hours=args.offset_server, stops_level=Decimal(args.stops_level),
    )  # fmt: skip
    report = build_report(result, cfg)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
