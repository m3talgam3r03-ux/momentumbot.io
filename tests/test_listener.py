"""Listener: nuovo, modificato, cancellato, arretrato, senza prezzi; latenza e heartbeat."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from momentum_master.decision.engine import Action, Reason
from momentum_master.exporter.models import ExportedMessage
from momentum_master.listener.core import ListenerCore
from momentum_master.store import Store
from test_engine import MARKET_IN_RANGE
from test_updates import cfg

SAMPLES = json.loads(
    (Path(__file__).parent / "data" / "wdt_real_samples.json").read_text(encoding="utf-8")
)
T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
# limit_exact: BUY LIMIT 4415.31 → prezzo sopra l'entrata
LIMIT_MARKET = replace(MARKET_IN_RANGE, bid=Decimal("4416.00"), ask=Decimal("4416.20"))
# plain_range: SELL 4313.68-4314.68 → bid dentro il range
RANGE_MARKET = replace(MARKET_IN_RANGE, bid=Decimal("4314.00"), ask=Decimal("4314.20"))


def msg(key_or_text: str, msg_id: int, at: datetime = T0, **kw: object) -> ExportedMessage:
    text = SAMPLES.get(key_or_text, key_or_text)
    return ExportedMessage(
        channel_id=1, msg_id=msg_id, date_utc=at, text=text, exported_at_utc=at, **kw
    )


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def setup(tmp_path: Path):
    market = {"snap": LIMIT_MARKET}
    clock = Clock(T0 + timedelta(seconds=1))
    seen: list = []
    core = ListenerCore(
        cfg(), Store(tmp_path / "db.sqlite"), market=lambda: market["snap"],
        on_decision=lambda m, d: seen.append(d), clock=clock,
    )  # fmt: skip
    return core, market, clock, seen


def test_live_limit_signal_opens_pending_and_measures_latency(setup) -> None:
    core, _, _, seen = setup
    d = core.on_new_message(msg("limit_exact", 10))
    assert d.action is Action.OPEN_PENDING
    assert seen == [d]
    assert core.stats.latencies_s == [1.0]
    assert "mediana 1.00 s" in core.heartbeat()


def test_edit_never_opens(setup) -> None:
    core, *_ = setup
    core.on_new_message(msg("limit_exact", 10))
    edited = msg("limit_exact", 10, edit_date_utc=T0 + timedelta(minutes=1))
    d = core.on_edited_message(edited)
    assert (d.action, d.reason) == (Action.REJECT, Reason.S8)


def test_backlog_is_recorded_never_executed(setup) -> None:
    core, *_ = setup
    d = core.on_backlog_message(msg("limit_exact", 10))
    assert (d.action, d.reason) == (Action.REJECT, Reason.S5)
    assert core.store.last_msg_id() == 10


def test_deleted_pending_signal_is_cancelled(setup) -> None:
    core, *_ = setup
    core.on_new_message(msg("limit_exact", 10))
    (d,) = core.on_deleted_messages([10])
    assert (d.action, d.target_msg_id) == (Action.CANCEL, 10)
    assert "(delete, modalità paper)" in core.store.explain(10)


def test_deleted_market_signal_only_notifies(setup) -> None:
    core, market, _, _ = setup
    market["snap"] = RANGE_MARKET
    assert core.on_new_message(msg("plain_range", 20)).action is Action.OPEN_MARKET
    (d,) = core.on_deleted_messages([20])
    assert (d.action, d.reason) == (Action.IGNORE, Reason.AMBIGUOUS)


def test_deleted_unknown_message(setup) -> None:
    core, *_ = setup
    (d,) = core.on_deleted_messages([999])
    assert d.action is Action.IGNORE


def test_without_market_source_signals_are_recorded_not_opened(tmp_path: Path) -> None:
    core = ListenerCore(cfg(), Store(tmp_path / "db.sqlite"), clock=lambda: T0)
    d = core.on_new_message(msg("limit_exact", 10))
    assert (d.action, d.reason) == (Action.REJECT, Reason.S7)
    assert "prezzo non disponibile" in d.details
    assert d.bid is None and d.spread is None


def test_cancel_reply_after_live_signal(setup) -> None:
    core, _, clock, _ = setup
    core.on_new_message(msg("limit_exact", 10))
    clock.now = T0 + timedelta(minutes=90)
    d = core.on_new_message(msg("cancelled", 11, at=clock.now, reply_to_msg_id=10))
    assert (d.action, d.target_msg_id) == (Action.CANCEL, 10)
