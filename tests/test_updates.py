"""Aggiornamenti: classificazione sui testi ESATTI dello storico, decisioni e collegamento."""

from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from momentum_master.classifier.classify import classify
from momentum_master.classifier.models import Category
from momentum_master.config import parse_config
from momentum_master.decision.engine import (
    Action,
    EngineState,
    MessageContext,
    Reason,
    SignalLink,
    decide,
)
from momentum_master.exporter.models import ExportedMessage
from momentum_master.pipeline import process_message
from momentum_master.store import Store, StoreError
from test_engine import MARKET_IN_RANGE

SAMPLES = json.loads(
    (Path(__file__).parent / "data" / "wdt_real_samples.json").read_text(encoding="utf-8")
)
CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "config.yaml").read_text(encoding="utf-8")
)
T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def msg(text: str, msg_id: int = 1, at: datetime = T0, **kw: object) -> ExportedMessage:
    return ExportedMessage(
        channel_id=1, msg_id=msg_id, date_utc=at, text=text, exported_at_utc=at, **kw
    )


def cfg(**targets: object):
    data = copy.deepcopy(CONFIG)
    data["targets"].update(targets)
    return parse_config(data)


# --- classificazione (testi esatti) --------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "category", "kind", "tp_hit"),
    [
        ("tp1_hit", Category.RESULT_ANNOUNCEMENT, "TP_HIT", 1),
        # L'etichetta "(appena preso metti BE)" nella prima riga NON è un'istruzione.
        ("tp1_hit_label_metti_be", Category.RESULT_ANNOUNCEMENT, "TP_HIT", 1),
        ("tp2_hit_be_it", Category.MOVE_BE, "TP_HIT_BE", 2),
        ("tp2_hit_be_en", Category.MOVE_BE, "TP_HIT_BE", 2),
        ("sl_hit", Category.RESULT_ANNOUNCEMENT, "SL_HIT", None),
        ("trade_complete", Category.CLOSE_FULL, "TRADE_COMPLETE", None),
        ("out_of_trade", Category.CLOSE_FULL, "OUT_OF_TRADE", None),
        ("cancelled", Category.CANCEL, "LIMIT_CANCELLED", None),
        ("limit_filled", Category.RESULT_ANNOUNCEMENT, "LIMIT_FILLED", None),
        ("heads_up", Category.AMBIGUOUS, "HEADS_UP", None),
        ("preparati", Category.NOISE, "PRE_ANNUNCIO", None),
        ("prep_old", Category.NOISE, "PRE_ANNUNCIO", None),
        ("weekly_results", Category.NOISE, "RIEPILOGO", None),
    ],
)
def test_real_update_messages(key: str, category: Category, kind: str, tp_hit: int | None) -> None:
    c = classify(msg(SAMPLES[key], reply_to_msg_id=500))
    assert (c.category, c.notes, c.tp_hit) == (category, kind, tp_hit)
    assert c.ref_msg_id == 500


def test_chart_caption_with_photo_in_reply_is_noise() -> None:
    c = classify(msg(SAMPLES["chart_caption"], media_type="photo", reply_to_msg_id=114))
    assert c.category is Category.NOISE


def test_same_caption_without_photo_or_reply_is_not_silenced() -> None:
    # Senza foto e senza risposta non vale la regola "didascalia": niente silenzio automatico.
    assert classify(msg(SAMPLES["chart_caption"])).category is not Category.NEW_SIGNAL_COMPLETE


@pytest.mark.parametrize(
    "key", ["rientra_927", "imposta_be_919", "italian_opening_922", "manual_buy_xau_1128"]
)
def test_manual_instructions_reach_the_admin(key: str) -> None:
    # Istruzioni scritte a mano (rientro, BE, apertura in italiano): mai eseguite, mai zitte.
    assert classify(msg(SAMPLES[key])).category is Category.AMBIGUOUS


def test_motivational_text_is_noise() -> None:
    assert classify(msg(SAMPLES["motivational"])).category is Category.NOISE


@pytest.mark.parametrize(
    "text",
    [
        "chiudete tutto adesso",
        "close now guys",
        "SL a 4300 per tutti",
        "spostate lo stop",
        "cancel the limit",
        "BE ora",
        "rientriamo",
        "buy again",
    ],
)
def test_instructions_are_never_generic_noise(text: str) -> None:
    for media, reply in ((None, None), ("photo", 10)):
        c = classify(msg(text, media_type=media, reply_to_msg_id=reply))
        assert c.category is not Category.NOISE, (text, media, reply)


# --- decisioni ------------------------------------------------------------------------------

LIVE = MessageContext(received_at_utc=T0 + timedelta(seconds=1))
LIMIT_LINK = SignalLink(400, "LIMIT")
MARKET_LINK = SignalLink(401, "MARKET")


def run(key: str, link: SignalLink | None, config=None, mctx=LIVE, state=None):
    c = classify(msg(SAMPLES[key], msg_id=900, reply_to_msg_id=link.signal_msg_id if link else 7))
    return decide(c, mctx, MARKET_IN_RANGE, state or EngineState(), config or cfg(), link)


def test_cancel_removes_linked_pending() -> None:
    d = run("cancelled", LIMIT_LINK)
    assert (d.action, d.reason, d.target_msg_id) == (Action.CANCEL, Reason.OK, 400)


def test_cancel_on_market_signal_only_notifies() -> None:
    d = run("cancelled", MARKET_LINK)
    assert (d.action, d.reason) == (Action.IGNORE, Reason.AMBIGUOUS)


@pytest.mark.parametrize("key", ["out_of_trade", "trade_complete"])
@pytest.mark.parametrize("link", [LIMIT_LINK, MARKET_LINK])
def test_close_acts_on_linked_signal(key: str, link: SignalLink) -> None:
    d = run(key, link)
    assert (d.action, d.reason, d.target_msg_id) == (Action.CLOSE, Reason.OK, link.signal_msg_id)


@pytest.mark.parametrize("key", ["cancelled", "out_of_trade"])
def test_update_without_open_signal_only_notifies(key: str) -> None:
    d = run(key, None)
    assert (d.action, d.reason) == (Action.IGNORE, Reason.AMBIGUOUS)
    assert "nessun segnale aperto collegato" in d.details


@pytest.mark.parametrize("key", ["tp2_hit_be_it", "tp2_hit_be_en", "tp1_hit"])
def test_break_even_is_off_by_default(key: str) -> None:
    d = run(key, MARKET_LINK)
    assert d.action is Action.IGNORE and "D5" in d.details


def test_break_even_when_enabled_after_tp2() -> None:
    config = cfg(be_after_tp=2)
    assert run("tp1_hit", MARKET_LINK, config).action is Action.IGNORE
    d = run("tp2_hit_be_en", MARKET_LINK, config)
    assert (d.action, d.target_msg_id) == (Action.MODIFY, 401)


def test_results_and_heads_up_never_act() -> None:
    assert run("sl_hit", MARKET_LINK).action is Action.IGNORE
    assert run("limit_filled", LIMIT_LINK).action is Action.IGNORE
    d = run("heads_up", LIMIT_LINK)
    assert (d.action, d.reason) == (Action.IGNORE, Reason.AMBIGUOUS)  # D4: solo notifica


@pytest.mark.parametrize(
    ("mctx", "reason"),
    [
        (MessageContext(received_at_utc=T0, event="edit"), Reason.S8),
        (MessageContext(received_at_utc=T0, is_live=False), Reason.S5),
        (MessageContext(received_at_utc=T0, is_forward=True), Reason.S5),
    ],
)
def test_updates_respect_safety_rules(mctx: MessageContext, reason: Reason) -> None:
    d = run("cancelled", LIMIT_LINK, mctx=mctx)
    assert (d.action, d.reason) == (Action.IGNORE, reason)


def test_update_already_processed() -> None:
    d = run("cancelled", LIMIT_LINK, state=EngineState(processed_msg_ids=frozenset({900})))
    assert d.reason is Reason.S6


# --- collegamento tramite registro (pipeline completa) --------------------------------------


def test_reply_to_second_copy_reaches_the_opened_signal(tmp_path: Path) -> None:
    store, config = Store(tmp_path / "db.sqlite"), cfg()
    limit = SAMPLES["limit_exact"]  # BUY LIMIT 4415.31
    # prezzo sopra l'entrata: BUY LIMIT valido
    market = replace(MARKET_IN_RANGE, bid=MARKET_IN_RANGE.bid + 280, ask=MARKET_IN_RANGE.ask + 280)
    t1, t2 = T0 + timedelta(seconds=10), T0 + timedelta(minutes=30)
    first = process_message(msg(limit, 10, T0), MessageContext(T0 + timedelta(seconds=1)),
                            market, config, store)  # fmt: skip
    copy_ = process_message(msg(limit, 11, t1), MessageContext(t1 + timedelta(seconds=1)),
                            market, config, store)  # fmt: skip
    cancel = process_message(
        msg(SAMPLES["cancelled"], 12, t2, reply_to_msg_id=11),  # risponde alla COPIA
        MessageContext(t2 + timedelta(seconds=1)), market, config, store,
    )  # fmt: skip
    assert first.action is Action.OPEN_PENDING
    assert (copy_.reason, copy_.duplicate_of) == (Reason.S11, 10)
    assert (cancel.action, cancel.target_msg_id) == (Action.CANCEL, 10)
    assert "Segnale su cui agire: 10" in store.explain(12)


def test_reply_to_rejected_signal_has_no_link(tmp_path: Path) -> None:
    store, config = Store(tmp_path / "db.sqlite"), cfg()
    far = replace(MARKET_IN_RANGE, bid=MARKET_IN_RANGE.bid + 50, ask=MARKET_IN_RANGE.ask + 50)
    process_message(msg(SAMPLES["plain_range"], 20, T0), MessageContext(T0), far, config, store)
    t = T0 + timedelta(minutes=5)
    d = process_message(msg(SAMPLES["out_of_trade"], 21, t, reply_to_msg_id=20),
                        MessageContext(t), far, config, store)  # fmt: skip
    assert (d.action, d.reason) == (Action.IGNORE, Reason.AMBIGUOUS)


def test_old_registry_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "vecchio.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE messages (id INTEGER)")
    db.execute("PRAGMA user_version = 1")
    db.commit()
    db.close()
    with pytest.raises(StoreError, match="schema v1"):
        Store(path)
