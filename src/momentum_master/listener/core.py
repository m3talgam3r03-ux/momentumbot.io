"""Nucleo del listener: cosa fare di ogni evento Telegram. Nessuna dipendenza da Telethon.

Eventi:
- nuovo messaggio dal vivo → classifica, decide, registra (in PAPER nessun ordine);
- messaggio modificato → registrato come "edit": non apre mai (S8);
- messaggio cancellato → se era un pendente aperto: CANCEL; se era a mercato: notifica;
- messaggi arretrati (arrivati mentre il bot era spento) → registrati con is_live=False:
  il motore non li esegue mai (S5).

Ogni decisione viene anche passata a ``on_decision`` (log, notifiche, executor futuro).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from momentum_master.config import AppConfig
from momentum_master.decision.engine import (
    Action,
    Decision,
    MarketSnapshot,
    MessageContext,
    Reason,
    decide_deletion,
)
from momentum_master.exporter.models import ExportedMessage
from momentum_master.pipeline import process_message
from momentum_master.store import Store

logger = logging.getLogger(__name__)

MarketProvider = Callable[[], MarketSnapshot | None]
DecisionSink = Callable[[ExportedMessage | None, Decision], None]


def _no_market() -> MarketSnapshot | None:
    return None


@dataclass
class ListenerStats:
    received: int = 0
    edits: int = 0
    deletions: int = 0
    backlog: int = 0
    latencies_s: list[float] = field(default_factory=list)

    def latency_summary(self) -> str:
        if not self.latencies_s:
            return "nessuna misura"
        ordered = sorted(self.latencies_s)
        p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
        return f"mediana {ordered[len(ordered) // 2]:.2f} s, 95° percentile {p95:.2f} s"


class ListenerCore:
    def __init__(
        self,
        cfg: AppConfig,
        store: Store,
        market: MarketProvider = _no_market,
        on_decision: DecisionSink | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.market = market
        self.on_decision = on_decision or (lambda _m, _d: None)
        self.clock = clock
        self.stats = ListenerStats()

    def _snapshot(self, now: datetime) -> MarketSnapshot:
        snap = self.market()
        if snap is not None:
            return snap
        # Senza fonte di prezzi l'ora del server non è nota: si usa UTC (solo per il registro).
        return MarketSnapshot.unavailable(now.replace(tzinfo=None))

    def _process(self, msg: ExportedMessage, mctx: MessageContext) -> Decision:
        decision = process_message(msg, mctx, self._snapshot(mctx.received_at_utc), self.cfg,
                                   self.store)  # fmt: skip
        self.on_decision(msg, decision)
        return decision

    def on_new_message(self, msg: ExportedMessage) -> Decision:
        now = self.clock()
        self.stats.received += 1
        self.stats.latencies_s.append((now - msg.date_utc).total_seconds())
        return self._process(
            msg, MessageContext(received_at_utc=now, is_forward=msg.is_forward, is_live=True)
        )

    def on_edited_message(self, msg: ExportedMessage) -> Decision:
        self.stats.edits += 1
        return self._process(msg, MessageContext(received_at_utc=self.clock(), event="edit"))

    def on_backlog_message(self, msg: ExportedMessage) -> Decision:
        """Messaggio recuperato all'avvio: si registra, non si esegue mai."""
        self.stats.backlog += 1
        return self._process(msg, MessageContext(received_at_utc=self.clock(), is_live=False))

    def on_deleted_messages(self, msg_ids: list[int]) -> list[Decision]:
        now = self.clock()
        decisions = []
        for msg_id in msg_ids:
            self.stats.deletions += 1
            decision = decide_deletion(
                msg_id, self.store.signal_link(msg_id), now, self.cfg.meta.version
            )
            self.store.record_deletion(msg_id, decision, deleted_at_utc=now,
                                       mode=self.cfg.mode.value)  # fmt: skip
            self.on_decision(None, decision)
            decisions.append(decision)
        return decisions

    def heartbeat(self) -> str:
        s = self.stats
        return (
            f"heartbeat: {s.received} messaggi dal vivo, {s.edits} modifiche, "
            f"{s.deletions} cancellazioni, {s.backlog} arretrati; latenza {s.latency_summary()}"
        )


def log_decision(msg: ExportedMessage | None, d: Decision) -> None:
    """Sink di default: una riga leggibile per ogni decisione (le notifiche arriveranno dopo)."""
    level = logging.WARNING if d.reason in (Reason.AMBIGUOUS, Reason.S8) else logging.INFO
    if d.action in (Action.OPEN_MARKET, Action.OPEN_PENDING, Action.CANCEL, Action.CLOSE):
        level = logging.WARNING
    first_line = msg.text.split("\n", 1)[0][:60] if msg and msg.text else ""
    logger.log(level, "msg %s → %s (%s) %s | %s", d.msg_id, d.action.value, d.reason.value,
               d.details, first_line)  # fmt: skip
