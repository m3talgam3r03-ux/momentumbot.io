"""Motore decisionale: un test per ogni reason_code, sui messaggi reali del catalogo."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml

from golden_messages import GOLDEN_OPENINGS, NON_OPENINGS_REAL
from momentum_master.classifier.classify import classify
from momentum_master.classifier.models import Side
from momentum_master.config import AppConfig, parse_config
from momentum_master.decision.engine import (
    Action,
    EngineState,
    MarketSnapshot,
    MessageContext,
    Reason,
    RecentSignal,
    decide,
)
from momentum_master.exporter.models import ExportedMessage

CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "config.yaml").read_text(encoding="utf-8")
)
PUBLISHED = datetime(2026, 10, 6, 12, 0, 0, tzinfo=UTC)  # martedì
RECEIVED = PUBLISHED + timedelta(seconds=2)
TEXT = {c["id"]: c["text"] for c in GOLDEN_OPENINGS}

# range_sell_1: SELL 4138.96-4139.96, SL 4147.96, TP1 4134.36
MARKET_IN_RANGE = MarketSnapshot(
    bid=D("4139.50"), ask=D("4139.75"), server_time=datetime(2026, 10, 6, 15, 0),
    trade_allowed=True, stops_level=D("0.20"),
    minutes_to_week_close=3000, minutes_since_week_open=3000,
)  # fmt: skip
# limit_sell_1: SELL LIMIT 4148.25, SL 4153.25, TP1 4145.75 → prezzo sotto l'entrata: valido
MARKET_BELOW_LIMIT = replace(MARKET_IN_RANGE, bid=D("4141.00"), ask=D("4141.25"))


def cfg(**changes: object) -> AppConfig:
    data = copy.deepcopy(CONFIG)
    for dotted, value in changes.items():
        section, key = dotted.split("__")
        data[section][key] = value
    return parse_config(data)


def classified(signal_id: str = "range_sell_1", text: str | None = None):
    msg = ExportedMessage(
        channel_id=1, msg_id=100, date_utc=PUBLISHED,
        text=text if text is not None else TEXT[signal_id], exported_at_utc=PUBLISHED,
    )  # fmt: skip
    return classify(msg)


def run(
    signal_id: str = "range_sell_1",
    *,
    market: MarketSnapshot = MARKET_IN_RANGE,
    state: EngineState | None = None,
    config: AppConfig | None = None,
    mctx: MessageContext | None = None,
    msg=None,
):
    return decide(
        msg or classified(signal_id),
        mctx or MessageContext(received_at_utc=RECEIVED),
        market,
        state or EngineState(),
        config or cfg(),
    )


# --- esiti positivi ------------------------------------------------------------------


def test_range_signal_in_range_opens_at_market_with_tp1() -> None:
    d = run()
    assert (d.action, d.reason) == (Action.OPEN_MARKET, Reason.OK)
    assert d.side is Side.SELL and d.order_type == "MARKET"
    assert d.entry_price == D("4139.50")  # SELL al bid
    assert (d.sl, d.tp, d.tp_index) == (D("4147.96"), D("4134.36"), 1)
    assert d.config_version == "0.1.0"


def test_limit_signal_becomes_pending_with_broker_expiry() -> None:
    d = run("limit_sell_1", market=MARKET_BELOW_LIMIT)
    assert (d.action, d.reason, d.order_type) == (Action.OPEN_PENDING, Reason.OK, "LIMIT")
    assert d.entry_price == D("4148.25")
    assert (d.sl, d.tp) == (D("4153.25"), D("4145.75"))
    assert d.expiry_utc == RECEIVED + timedelta(minutes=90)


def test_pending_expiry_is_cut_before_rollover() -> None:
    late = replace(MARKET_BELOW_LIMIT, server_time=datetime(2026, 10, 6, 23, 0))
    d = run("limit_sell_1", market=late)
    assert d.expiry_utc == RECEIVED + timedelta(minutes=50)  # rollover alle 23:50


def test_other_tp_by_config() -> None:
    d = run(config=cfg(targets__tp_index=2))
    assert (d.tp, d.tp_index) == (D("4130.96"), 2)


def test_decision_is_deterministic() -> None:
    assert run() == run()


# --- non segnali ------------------------------------------------------------------------


@pytest.mark.parametrize("case", NON_OPENINGS_REAL, ids=[c["id"] for c in NON_OPENINGS_REAL])
def test_real_non_signals_are_ignored(case: dict) -> None:
    d = run(msg=classified(text=case["text"]))
    assert d.action is Action.IGNORE
    assert not d.is_open


def test_noise_is_not_a_signal() -> None:
    noise = classified().model_copy(update={"category": "NOISE"})
    assert run(msg=noise).reason is Reason.NOT_A_SIGNAL


# --- regole di sicurezza S1-S11 -----------------------------------------------------------


def test_s8_edit_never_opens() -> None:
    d = run(mctx=MessageContext(received_at_utc=RECEIVED, event="edit"))
    assert (d.action, d.reason) == (Action.REJECT, Reason.S8)


def test_s6_same_message_twice() -> None:
    d = run(state=EngineState(processed_msg_ids=frozenset({100})))
    assert d.reason is Reason.S6


@pytest.mark.parametrize(
    ("mctx", "fragment"),
    [
        (MessageContext(received_at_utc=RECEIVED, is_forward=True), "inoltrato"),
        (MessageContext(received_at_utc=RECEIVED, is_live=False), "arretrato"),
        (MessageContext(received_at_utc=PUBLISHED + timedelta(seconds=31)), "vecchio"),
    ],
)
def test_s5_old_forwarded_or_backlog(mctx: MessageContext, fragment: str) -> None:
    d = run(mctx=mctx)
    assert d.reason is Reason.S5 and fragment in d.details


def test_s1_requested_tp_missing() -> None:
    d = run(config=cfg(targets__tp_index=5))  # TP5 è "OPEN"
    assert d.reason is Reason.S1


def test_s7_market_closed() -> None:
    assert run(market=replace(MARKET_IN_RANGE, trade_allowed=False)).reason is Reason.S7


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"server_time": datetime(2026, 10, 6, 23, 55)}, "rollover"),
        ({"server_time": datetime(2026, 10, 7, 0, 5)}, "rollover"),  # a cavallo di mezzanotte
        ({"minutes_to_week_close": 10}, "chiusura settimanale"),
        ({"minutes_since_week_open": 10}, "apertura settimanale"),
        ({"minutes_to_week_close": None}, "sconosciuti"),
    ],
)
def test_s9_risky_windows(changes: dict, fragment: str) -> None:
    d = run(market=replace(MARKET_IN_RANGE, **changes))
    assert d.reason is Reason.S9 and fragment in d.details


def test_s10_emergency_spread_beats_filters() -> None:
    wide = replace(MARKET_IN_RANGE, bid=D("4139.00"), ask=D("4140.60"))  # spread 1,60
    assert run(market=wide).reason is Reason.S10  # S10 prima di F8


@pytest.mark.parametrize(
    "update",
    [
        {"sl": D("4130.00")},  # SELL con SL sotto l'entrata
        {"tps": [D("4140.50"), D("4130.96")]},  # SELL con TP1 sopra l'entrata
    ],
)
def test_s2_incoherent_levels(update: dict) -> None:
    assert run(msg=classified().model_copy(update=update)).reason is Reason.S2


def test_s3_entry_far_from_price_typo() -> None:
    # "2560 invece di 2650": entrata a 4039 con prezzo a 4139
    typo = classified().model_copy(
        update={"entry_min": D("4038.96"), "entry_max": D("4039.96"), "sl": D("4047.96"),
                "tps": [D("4034.36")]}
    )  # fmt: skip
    assert run(msg=typo).reason is Reason.S3


def test_s4_stop_too_close_for_broker() -> None:
    assert run(market=replace(MARKET_IN_RANGE, stops_level=D("8.00"))).reason is Reason.S4


def test_s11_duplicate_post_is_rejected() -> None:
    previous = RecentSignal(
        99, Side.SELL, D("4138.96"), D("4147.96"), RECEIVED - timedelta(seconds=20)
    )
    d = run(state=EngineState(recent_signals=(previous,)))
    assert d.reason is Reason.S11


def test_s11_old_duplicate_outside_window_is_new() -> None:
    previous = RecentSignal(
        99, Side.SELL, D("4138.96"), D("4147.96"), RECEIVED - timedelta(hours=1)
    )
    assert run(state=EngineState(recent_signals=(previous,))).action is Action.OPEN_MARKET


# --- filtri F --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("signal", "market", "config", "reason"),
    [
        ("range_sell_1", MARKET_IN_RANGE, {"filters__direction": "buy_only"}, Reason.F2),
        ("limit_sell_1", MARKET_BELOW_LIMIT,
         {"filters__order_type_mode": "market_only"}, Reason.F1),
        ("range_sell_1", MARKET_IN_RANGE, {"filters__order_type_mode": "pending_only"}, Reason.F1),
        ("range_sell_1", MARKET_IN_RANGE, {"filters__sl_distance_max": 5}, Reason.F3),
        ("range_sell_1", MARKET_IN_RANGE, {"filters__sl_distance_min": 10}, Reason.F3),
        ("range_sell_1", MARKET_IN_RANGE, {"filters__exclude_keywords": ["inpulse"]}, Reason.F12),
        ("range_sell_1", MARKET_IN_RANGE,
         {"filters__trading_hours_rome": {"start": "08:00", "end": "12:00"}}, Reason.F9),
        ("range_sell_1", MARKET_IN_RANGE, {"filters__max_spread": 0.10}, Reason.F8),
    ],
)  # fmt: skip
def test_filters(signal: str, market: MarketSnapshot, config: dict, reason: Reason) -> None:
    assert run(signal, market=market, config=cfg(**config)).reason is reason


def test_f9_inside_hours_passes() -> None:
    # 12:00 UTC = 14:00 a Roma (ora legale)
    hours = cfg(filters__trading_hours_rome={"start": "13:00", "end": "15:00"})
    assert run(config=hours).action is Action.OPEN_MARKET


@pytest.mark.parametrize("state", [EngineState(trades_today=10), EngineState(open_positions=2)])
def test_f11_daily_and_open_limits(state: EngineState) -> None:
    assert run(state=state).reason is Reason.F11


@pytest.mark.parametrize(
    ("bid", "ask"),
    [(D("4138.90"), D("4139.10")), (D("4140.00"), D("4140.20"))],  # sotto / sopra il range
)
def test_f5_range_out_of_range_is_discarded(bid: D, ask: D) -> None:
    d = run(market=replace(MARKET_IN_RANGE, bid=bid, ask=ask))
    assert d.reason is Reason.F5 and "scartato" in d.details


def test_f5_limit_already_past_entry() -> None:
    past = replace(MARKET_IN_RANGE, bid=D("4148.50"), ask=D("4148.75"))  # SELL LIMIT 4148.25
    assert run("limit_sell_1", market=past).reason is Reason.F5


def test_buy_range_uses_ask() -> None:
    # range_buy_2: BUY 4160.16-4161.16, SL 4155.66
    market = replace(MARKET_IN_RANGE, bid=D("4160.90"), ask=D("4161.10"))
    d = run("range_buy_2", market=market)
    assert d.action is Action.OPEN_MARKET and d.entry_price == D("4161.10")


def test_every_reason_code_is_tested() -> None:
    """Promemoria: se si aggiunge un reason_code, serve il suo test."""
    tested = {
        "OK", "NOT_A_SIGNAL", "AMBIGUOUS", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
        "S9", "S10", "S11", "F1", "F2", "F3", "F5", "F8", "F9", "F11", "F12",
    }  # fmt: skip
    assert {r.value for r in Reason} == tested
