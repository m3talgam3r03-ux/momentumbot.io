"""Pipeline di un messaggio: classifica → decide → registra.

Collega i pezzi puri (classificatore, motore) al registro. Non invia ordini: in PAPER la
decisione viene solo registrata. L'esecuzione su MT5 arriverà al passo 6 e partirà da qui
solo se ``cfg.mode`` non è PAPER.
"""

from __future__ import annotations

from momentum_master.classifier.classify import classify
from momentum_master.config import AppConfig
from momentum_master.decision.engine import Decision, MarketSnapshot, MessageContext, decide
from momentum_master.exporter.models import ExportedMessage
from momentum_master.store import Store


def process_message(
    msg: ExportedMessage,
    mctx: MessageContext,
    market: MarketSnapshot,
    cfg: AppConfig,
    store: Store,
) -> Decision:
    posters = cfg.telegram.channel_poster_ids
    authorized = frozenset(posters) if posters is not None else None
    classified = classify(msg, authorized)
    state = store.engine_state(mctx.received_at_utc, cfg.safety.dedup_window_s)
    decision = decide(classified, mctx, market, state, cfg)
    store.record(
        msg,
        classified,
        decision,
        event=mctx.event,
        received_at_utc=mctx.received_at_utc,
        mode=cfg.mode.value,
    )
    return decision
