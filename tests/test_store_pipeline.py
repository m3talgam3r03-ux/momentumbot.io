"""Registro SQLite e pipeline completa (classifica → decide → registra) in PAPER."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from golden_messages import GOLDEN_OPENINGS
from momentum_master.config import parse_config
from momentum_master.decision.engine import Action, MessageContext, Reason
from momentum_master.exporter.models import ExportedMessage
from momentum_master.pipeline import process_message
from momentum_master.store import Store
from test_engine import MARKET_IN_RANGE

CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "config.yaml").read_text(encoding="utf-8")
)
T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
RANGE_SELL = next(c["text"] for c in GOLDEN_OPENINGS if c["id"] == "range_sell_1")


def msg(msg_id: int, text: str, at: datetime, sender: int | None = 777) -> ExportedMessage:
    return ExportedMessage(
        channel_id=1, msg_id=msg_id, date_utc=at, text=text, exported_at_utc=at, sender_id=sender
    )


def config(**telegram: object):
    data = copy.deepcopy(CONFIG)
    data["telegram"].update(telegram)
    return parse_config(data)


def live(at: datetime) -> MessageContext:
    return MessageContext(received_at_utc=at + timedelta(seconds=1))


def test_duplicate_post_opens_once(tmp_path: Path) -> None:
    store, cfg = Store(tmp_path / "db.sqlite"), config()
    first = process_message(msg(1, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, cfg, store)
    t1 = T0 + timedelta(seconds=15)
    second = process_message(msg(2, RANGE_SELL, t1), live(t1), MARKET_IN_RANGE, cfg, store)
    assert first.action is Action.OPEN_MARKET
    assert (second.action, second.reason) == (Action.REJECT, Reason.S11)


def test_duplicate_of_a_rejected_signal_is_still_a_duplicate(tmp_path: Path) -> None:
    store, cfg = Store(tmp_path / "db.sqlite"), config()
    out_of_range = replace(
        MARKET_IN_RANGE, bid=MARKET_IN_RANGE.bid + 5, ask=MARKET_IN_RANGE.ask + 5
    )
    first = process_message(msg(1, RANGE_SELL, T0), live(T0), out_of_range, cfg, store)
    t1 = T0 + timedelta(seconds=15)
    second = process_message(msg(2, RANGE_SELL, t1), live(t1), MARKET_IN_RANGE, cfg, store)
    assert first.reason is Reason.F5
    assert second.reason is Reason.S11  # il prezzo è rientrato, ma è lo stesso segnale


def test_unauthorized_sender_in_group(tmp_path: Path) -> None:
    store, cfg = Store(tmp_path / "db.sqlite"), config(channel_poster_ids=[777])
    d = process_message(msg(1, RANGE_SELL, T0, sender=999), live(T0), MARKET_IN_RANGE, cfg, store)
    assert (d.action, d.reason) == (Action.IGNORE, Reason.NOT_A_SIGNAL)
    assert "non autorizzato" in d.details


def test_redelivered_message_is_recorded_once(tmp_path: Path) -> None:
    store, cfg = Store(tmp_path / "db.sqlite"), config()
    process_message(msg(1, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, cfg, store)
    again = process_message(msg(1, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, cfg, store)
    assert again.reason is Reason.S6
    assert store.explain(1).count("=== Messaggio 1") == 1


def test_explain_reconstructs_the_whole_chain(tmp_path: Path) -> None:
    store, cfg = Store(tmp_path / "db.sqlite"), config()
    process_message(msg(1, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, cfg, store)
    text = store.explain(1)
    for expected in (
        "modalità paper", "ENTRY RANGE:: 4138.96 - 4139.96", "Categoria: NEW_SIGNAL_COMPLETE",
        "Decisione: OPEN_MARKET (OK)", "Ordine: MARKET @ 4139.50", "TP1 4134.36", "config 0.1.0",
    ):  # fmt: skip
        assert expected in text, expected
    assert "Nessun evento" in store.explain(999)


def test_store_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    store, cfg = Store(path), config()
    process_message(msg(1, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, cfg, store)
    store.close()
    state = Store(path).engine_state(T0 + timedelta(minutes=1), dedup_window_s=600)
    assert 1 in state.processed_msg_ids
    assert state.trades_today == 1
    assert len(state.recent_signals) == 1


def test_explain_command_line(tmp_path: Path, capsys) -> None:
    from momentum_master.store import main

    path = tmp_path / "db.sqlite"
    store = Store(path)
    process_message(msg(5, RANGE_SELL, T0), live(T0), MARKET_IN_RANGE, config(), store)
    store.close()
    assert main([str(path), "5"]) == 0
    assert "Decisione: OPEN_MARKET" in capsys.readouterr().out
    assert main([str(tmp_path / "manca.sqlite"), "5"]) == 1
    assert main([str(path)]) == 2
