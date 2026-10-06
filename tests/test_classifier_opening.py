"""Classificatore dei messaggi di apertura: test golden (messaggi reali) e test negativi."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from golden_messages import GOLDEN_OPENINGS, NON_OPENINGS_REAL
from momentum_master.classifier.classify import classify
from momentum_master.classifier.models import Category
from momentum_master.exporter.models import ExportedMessage

T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def msg(text: str, msg_id: int = 1, **kwargs: object) -> ExportedMessage:
    return ExportedMessage(
        channel_id=1, msg_id=msg_id, date_utc=T0, text=text, exported_at_utc=T0, **kwargs
    )


@pytest.mark.parametrize("case", GOLDEN_OPENINGS, ids=[c["id"] for c in GOLDEN_OPENINGS])
def test_golden_openings(case: dict) -> None:
    result = classify(msg(case["text"]))
    assert result.category is Category.NEW_SIGNAL_COMPLETE, result.notes
    assert result.side == case["side"]
    assert result.order_hint == case["order_hint"]
    assert (result.entry_min, result.entry_max) == case["entry"]
    assert result.sl == case["sl"]
    assert result.tps == case["tps"]
    assert result.tps[0] == case["tps"][0]  # TP1: quello che si usa
    assert result.tp_open is case["tp_open"]
    assert result.confidence == 1.0


LIMIT_BUY = GOLDEN_OPENINGS[0]["text"]
RANGE_SELL = next(c["text"] for c in GOLDEN_OPENINGS if c["id"] == "range_sell_1")


@pytest.mark.parametrize(
    ("label", "text", "expected_note"),
    [
        ("senza SL", LIMIT_BUY.replace("SL ❌: 4153.16\n\n", ""), "SL"),
        ("SL doppio", LIMIT_BUY.replace("SL ❌: 4153.16", "SL ❌: 4153.16\nSL: 4150"), "SL"),
        ("senza ENTRY", LIMIT_BUY.replace("ENTRY: 4158.16\n\n", ""), "ENTRY"),
        ("due ENTRY", LIMIT_BUY.replace("ENTRY: 4158.16", "ENTRY: 4158.16\nENTRY: 4150"), "ENTRY"),
        ("prezzo ambiguo", LIMIT_BUY.replace("SL ❌: 4153.16", "SL ❌: 4,153"), "SL"),
        ("prezzo sporco", LIMIT_BUY.replace("ENTRY: 4158.16", "ENTRY: 4158.16?"), "ENTRY"),
        ("TP fuori ordine", LIMIT_BUY.replace("TP3✅: 4168.16", "TP3✅: 4161.00"), "TP"),
        ("TP mancante", LIMIT_BUY.replace("TP2 (metti a BE)✅: 4163.16\n", ""), "TP"),
        ("senza TP", LIMIT_BUY.split("TP1")[0], "TP"),
        ("TP1 OPEN", LIMIT_BUY.replace("TP1 (valuta il BE)✅: 4160.66", "TP1✅: OPEN"), "TP1"),
        (
            "range dentro un limit",
            LIMIT_BUY.replace("ENTRY: 4158.16", "ENTRY RANGE:: 4158 - 4159"),
            "ENTRY",
        ),
        ("range illeggibile", RANGE_SELL.replace("4139.96", "4139,9x"), "ENTRY"),
        (
            "buy stop",
            LIMIT_BUY.replace("LIMIT ORDER — BUY", "LIMIT ORDER — BUY STOP"),
            "catalogato",
        ),
        (
            "stop order",
            LIMIT_BUY.replace("XAUUSD (GOLD) ⏳", "XAUUSD (GOLD) STOP ORDER ⏳", 1),
            "STOP",
        ),
    ],
)
def test_broken_openings_are_never_signals(label: str, text: str, expected_note: str) -> None:
    result = classify(msg(text))
    assert result.category is Category.AMBIGUOUS, f"{label}: {result}"
    assert expected_note in result.notes


@pytest.mark.parametrize(
    "text",
    [
        "TP1 ✅ hit! +25 pips 🔥",
        "BUY XAUUSD now? Let's see what the market does",  # nessuna riga ENTRY/SL/TP
        "Analisi: XAUUSD potrebbe salire verso 4170, supporto a 4150",
        "Unisciti al nostro VIP! Link in bio",
        "ENTRY: 4158.16\nSL: 4153.16\nTP1: 4160.66",  # livelli senza intestazione
        "",
    ],
)
def test_non_openings_are_not_signals(text: str) -> None:
    result = classify(msg(text))
    assert result.category is not Category.NEW_SIGNAL_COMPLETE


@pytest.mark.parametrize("case", NON_OPENINGS_REAL, ids=[c["id"] for c in NON_OPENINGS_REAL])
def test_real_non_openings_are_never_signals(case: dict) -> None:
    result = classify(msg(case["text"]))
    assert result.category is not Category.NEW_SIGNAL_COMPLETE, result
    assert result.category == case["future"], result.notes


def test_duplicate_openings_are_both_recognized() -> None:
    # Il canale pubblica le aperture a range DUE volte: il classificatore le riconosce
    # entrambe; sarà la regola S11 (dedup) del decision_engine a eseguirne una sola.
    text = next(c["text"] for c in GOLDEN_OPENINGS if c["id"] == "range_buy_2")
    first, second = classify(msg(text, msg_id=1)), classify(msg(text, msg_id=2))
    assert first.category is second.category is Category.NEW_SIGNAL_COMPLETE
    assert (first.side, first.entry_min, first.sl) == (second.side, second.entry_min, second.sl)


def test_header_must_be_first_line() -> None:
    text = "Buongiorno a tutti!\n" + LIMIT_BUY
    assert classify(msg(text)).category is Category.AMBIGUOUS


def test_screenshot_only_is_ambiguous() -> None:
    result = classify(msg("", media_type="MessageMediaPhoto"))
    assert result.category is Category.AMBIGUOUS
    assert "OCR" in result.notes


def test_service_message_is_noise() -> None:
    result = classify(msg("", is_service=True, service_action="MessageActionPinMessage"))
    assert result.category is Category.NOISE


def test_commentary_with_trading_words_is_ignored() -> None:
    noisy = LIMIT_BUY.replace(
        "classic break and retest", "SL: 1000 TP1: 9999 sell now classic break and retest"
    )
    result = classify(msg(noisy))
    assert result.category is Category.NEW_SIGNAL_COMPLETE
    assert result.sl == GOLDEN_OPENINGS[0]["sl"]


def test_raw_text_is_preserved() -> None:
    assert classify(msg(LIMIT_BUY)).raw_text == LIMIT_BUY
