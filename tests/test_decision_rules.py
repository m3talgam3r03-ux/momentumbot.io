"""Regole decise da Lorenzo il 2026-10-06: D1 (mittente), D2 (range), D5 (TP e BE)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from golden_messages import GOLDEN_OPENINGS
from momentum_master.classifier.classify import classify
from momentum_master.classifier.models import Category, Side
from momentum_master.decision.entry import check_range_entry
from momentum_master.decision.targets import (
    TargetsConfig,
    break_even_price,
    select_take_profit,
    should_move_to_break_even,
)
from momentum_master.exporter.models import ExportedMessage

T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
OPENING = GOLDEN_OPENINGS[0]["text"]
MOMENTUM_ID = 777
TPS = [D("4160.66"), D("4163.16"), D("4168.16"), D("4173.16")]


def msg(sender_id: int | None) -> ExportedMessage:
    return ExportedMessage(
        channel_id=1, msg_id=1, date_utc=T0, text=OPENING, exported_at_utc=T0, sender_id=sender_id
    )


# --- D1: solo il mittente autorizzato -----------------------------------------------


def test_authorized_sender_signal_is_recognized() -> None:
    result = classify(msg(MOMENTUM_ID), frozenset({MOMENTUM_ID}))
    assert result.category is Category.NEW_SIGNAL_COMPLETE


@pytest.mark.parametrize("sender", [123, None])
def test_other_senders_never_produce_signals(sender: int | None) -> None:
    result = classify(msg(sender), frozenset({MOMENTUM_ID}))
    assert result.category is Category.NOISE
    assert "non autorizzato" in result.notes


def test_empty_allowlist_blocks_everything() -> None:
    assert classify(msg(MOMENTUM_ID), frozenset()).category is Category.NOISE


# --- D2: prezzo fuori dal range → scarto -------------------------------------------

RANGE = (D("4138.96"), D("4139.96"))


@pytest.mark.parametrize(
    ("side", "bid", "ask", "inside"),
    [
        (Side.SELL, D("4139.50"), D("4139.80"), True),  # SELL usa il bid
        (Side.SELL, D("4138.96"), D("4139.30"), True),  # bordo incluso
        (Side.SELL, D("4138.95"), D("4139.20"), False),  # 1 centesimo sotto
        (Side.SELL, D("4140.10"), D("4140.40"), False),  # sopra
        (Side.BUY, D("4139.50"), D("4139.96"), True),  # BUY usa l'ask, bordo incluso
        (Side.BUY, D("4139.80"), D("4140.00"), False),  # ask oltre il range
    ],
)
def test_range_entry(side: Side, bid: D, ask: D, inside: bool) -> None:
    check = check_range_entry(side, *RANGE, bid=bid, ask=ask)
    assert check.inside is inside
    assert check.execution_price == (ask if side is Side.BUY else bid)
    if not inside:
        assert "scartato" in check.reason


def test_range_tolerance_is_explicit() -> None:
    check = check_range_entry(Side.SELL, *RANGE, bid=D("4140.20"), ask=D("4140.50"),
                              tolerance=D("0.30"))  # fmt: skip
    assert check.inside


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bid": D("4140"), "ask": D("4139")},  # bid > ask
        {"bid": D("4139"), "ask": D("4140"), "tolerance": D("-1")},
    ],
)
def test_range_entry_rejects_invalid_input(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        check_range_entry(Side.SELL, *RANGE, **kwargs)


# --- D5: TP configurabile, BE spento di default --------------------------------------


def test_default_is_tp1_and_no_break_even() -> None:
    cfg = TargetsConfig()
    choice = select_take_profit(TPS, cfg)
    assert (choice.price, choice.index_used) == (D("4160.66"), 1)
    assert not any(should_move_to_break_even(n, cfg) for n in range(1, 6))


@pytest.mark.parametrize(("index", "expected"), [(2, "4163.16"), (3, "4168.16"), (4, "4173.16")])
def test_other_tp_by_config(index: int, expected: str) -> None:
    assert select_take_profit(TPS, TargetsConfig(tp_index=index)).price == D(expected)


def test_missing_tp_rejected_by_default() -> None:
    choice = select_take_profit(TPS, TargetsConfig(tp_index=5))  # TP5 è "OPEN" → assente
    assert not choice.ok
    assert "TP5 assente" in choice.reason


def test_missing_tp_can_fall_back_to_last() -> None:
    choice = select_take_profit(TPS, TargetsConfig(tp_index=5, on_missing_tp="use_last_available"))
    assert (choice.price, choice.index_used) == (D("4173.16"), 4)


def test_no_tps_never_ok() -> None:
    assert not select_take_profit([], TargetsConfig()).ok


def test_break_even_when_enabled() -> None:
    cfg = TargetsConfig(be_after_tp=2, be_offset=D("0.20"))
    assert not should_move_to_break_even(1, cfg)
    assert should_move_to_break_even(2, cfg)
    assert break_even_price(Side.BUY, D("4160.70"), cfg) == D("4160.90")
    assert break_even_price(Side.SELL, D("4139.20"), cfg) == D("4139.00")


@pytest.mark.parametrize("bad", [{"tp_index": 0}, {"tp_index": 6}, {"be_offset": D("-1")}])
def test_invalid_targets_config_is_refused(bad: dict) -> None:
    with pytest.raises(ValueError):
        TargetsConfig(**bad)
