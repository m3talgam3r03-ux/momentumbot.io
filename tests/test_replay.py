"""Replay: simulazione degli esiti, serie di prezzi, pipeline completa, export MT5."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml

from momentum_master.classifier.models import Side
from momentum_master.config import parse_config
from momentum_master.decision.engine import Action, Reason
from momentum_master.exporter.models import ExportedMessage
from momentum_master.replay.export_mt5 import estimate_server_offset_hours, rates_to_rows
from momentum_master.replay.prices import Bar, PriceSeries, load_bars_csv
from momentum_master.replay.run import build_report, run_replay
from momentum_master.replay.simulate import Outcome, TradeSpec, simulate

SAMPLES = json.loads(
    (Path(__file__).parent / "data" / "wdt_real_samples.json").read_text(encoding="utf-8")
)
CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "config.yaml").read_text(encoding="utf-8")
)
START = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)  # martedì
SPREAD = D("0.20")


def series(prices: list[tuple[str, str, str, str]], start: datetime = START) -> PriceSeries:
    bars = [
        Bar(start + timedelta(minutes=i), D(o), D(h), D(lo), D(c), SPREAD)
        for i, (o, h, lo, c) in enumerate(prices)
    ]
    return PriceSeries(bars)


def flat(price: str, minutes: int) -> list[tuple[str, str, str, str]]:
    return [(price, price, price, price)] * minutes


def spec(side: Side, entry: str, sl: str, tp: str, kind: str = "MARKET", expiry_min: int = 0):
    decided = START + timedelta(seconds=30)  # dentro la prima barra
    expiry = decided + timedelta(minutes=expiry_min) if expiry_min else None
    return TradeSpec(1, side, kind, D(entry), D(sl), D(tp), decided, expiry)


# --- simulazione ---------------------------------------------------------------------------


def test_buy_reaches_tp() -> None:
    s = series([*flat("100", 2), ("100", "103", "99.5", "102")])
    r = simulate(spec(Side.BUY, "100", "98", "102.5"), s)
    assert (r.outcome, r.exit_price) == (Outcome.TP, D("102.5"))
    assert r.r == D("1.25")


def test_sl_and_tp_in_same_bar_counts_as_sl() -> None:
    s = series([*flat("100", 1), ("100", "103", "97", "100")])
    r = simulate(spec(Side.BUY, "100", "98", "102"), s)
    assert (r.outcome, r.r) == (Outcome.SL, D("-1"))


def test_decision_minute_is_not_used() -> None:
    # La barra del minuto della decisione tocca lo SL: non conta (niente sguardo in avanti).
    s = series([("100", "100", "90", "100"), ("100", "103", "99", "103")])
    assert simulate(spec(Side.BUY, "100", "98", "102"), s).outcome is Outcome.TP


def test_sell_exits_at_ask() -> None:
    # SELL TP 98: il bid tocca 97.9 ma l'ask (bid + 0.20) arriva solo a 98.10 → niente TP.
    s = series([*flat("100", 1), ("100", "100", "97.9", "99"), ("99", "99", "97.7", "98")])
    r = simulate(spec(Side.SELL, "100", "102", "98"), s)
    assert r.outcome is Outcome.TP and r.exit_at == START + timedelta(minutes=3)


def test_sell_stopped_by_spread() -> None:
    # SELL SL 102: il bid massimo è 101.85, ma l'ask (101.85 + 0.20) supera lo SL.
    s = series([*flat("100", 1), ("100", "101.85", "100", "101")])
    assert simulate(spec(Side.SELL, "100", "102", "98"), s).outcome is Outcome.SL


def test_buy_limit_fills_then_tp() -> None:
    s = series([*flat("101", 2), ("101", "101", "99.7", "100"), ("100", "103", "100", "103")])
    r = simulate(spec(Side.BUY, "100", "98", "102", "LIMIT", 60), s)
    assert r.outcome is Outcome.TP and r.filled_at == START + timedelta(minutes=2)


def test_limit_sl_in_fill_bar() -> None:
    s = series([*flat("101", 1), ("101", "101", "97", "99")])
    assert simulate(spec(Side.BUY, "100", "98", "102", "LIMIT", 60), s).outcome is Outcome.SL


def test_limit_expires_unfilled() -> None:
    s = series(flat("101", 30))
    r = simulate(spec(Side.BUY, "100", "98", "102", "LIMIT", 10), s)
    assert r.outcome is Outcome.NOT_FILLED and r.r is None


def test_provider_close_exits_at_next_open() -> None:
    s = series([*flat("100", 3), ("100.5", "101", "100", "101"), *flat("101", 5)])
    cutoff = START + timedelta(minutes=2, seconds=20)
    r = simulate(spec(Side.BUY, "100", "98", "105"), s, cutoff=cutoff)
    # Prima barra dopo il messaggio (2:20) = minuto 3, che apre a 100.5.
    assert (r.outcome, r.exit_price) == (Outcome.CLOSED_BY_PROVIDER, D("100.5"))


def test_cancel_before_fill() -> None:
    s = series(flat("101", 10))
    r = simulate(spec(Side.BUY, "100", "98", "102", "LIMIT", 60), s,
                 cutoff=START + timedelta(minutes=5))  # fmt: skip
    assert r.outcome is Outcome.NOT_FILLED


def test_open_at_end_of_data() -> None:
    assert simulate(spec(Side.BUY, "100", "98", "102"), series(flat("100", 5))).outcome is (
        Outcome.OPEN_AT_END
    )


# --- serie di prezzi --------------------------------------------------------------------------


def test_snapshot_open_closed_and_week_bounds() -> None:
    s = series(flat("100", 180))
    snap = s.snapshot(START + timedelta(minutes=60, seconds=5), 3, D("0.1"))
    assert snap.trade_allowed and (snap.bid, snap.ask) == (D("100"), D("100.20"))
    assert (snap.minutes_since_week_open, snap.minutes_to_week_close) == (60, 119)
    assert snap.server_time == datetime(2026, 10, 6, 15, 0, 5)
    closed = s.snapshot(START + timedelta(hours=10), 3, D("0.1"))
    assert not closed.trade_allowed


def test_weeks_split_on_long_gap() -> None:
    bars = [Bar(START, D(1), D(1), D(1), D(1), SPREAD),
            Bar(START + timedelta(hours=48), D(1), D(1), D(1), D(1), SPREAD)]  # fmt: skip
    snap = PriceSeries(bars).snapshot(START + timedelta(hours=48, seconds=10), 0, D(0))
    assert snap.minutes_since_week_open == 0


def test_csv_loading_and_validation(tmp_path: Path) -> None:
    good = tmp_path / "p.csv"
    good.write_text("time_utc,open,high,low,close,spread\n"
                    "2026-10-06T11:00:00+00:00,1,2,0.5,1.5,0.2\n", encoding="utf-8")  # fmt: skip
    assert load_bars_csv(good)[0].high == D("2")
    bad = tmp_path / "b.csv"
    bad.write_text("time_utc,open,high,low,close,spread\n"
                   "2026-10-06T11:00:00+00:00,1,0.9,0.5,1.5,0.2\n", encoding="utf-8")  # fmt: skip
    with pytest.raises(ValueError, match=r"b\.csv:2"):
        load_bars_csv(bad)


# --- pipeline completa ------------------------------------------------------------------------


def msg(text: str, msg_id: int, minute: int, **kw: object) -> ExportedMessage:
    at = START + timedelta(minutes=minute)
    return ExportedMessage(channel_id=1, msg_id=msg_id, date_utc=at, text=text,
                           exported_at_utc=at, **kw)  # fmt: skip


def cfg(**filters: object):
    data = copy.deepcopy(CONFIG)
    data["filters"].update(filters)
    return parse_config(data)


def test_replay_range_signal_duplicate_and_tp1() -> None:
    # plain_range: SELL 4313.68-4314.68, SL 4322.68, TP1 4309.08
    prices = [*flat("4314.00", 61), ("4314", "4314", "4308.50", "4309"), *flat("4309", 120)]
    result = run_replay(
        [msg(SAMPLES["plain_range"], 1, 60), msg(SAMPLES["plain_range"], 2, 60)],
        series(prices), cfg(), server_offset_hours=3,
    )  # fmt: skip
    assert result.decisions[("OPEN_MARKET", "OK")] == 1
    assert result.decisions[("REJECT", "S11")] == 1
    (trade,) = result.trades.values()
    assert trade.outcome is Outcome.TP and trade.spec.entry == D("4314.00")
    report = build_report(result, cfg())
    assert "| TP | 1 |" in report and "Win rate (R > 0) | 100.0%" in report


def test_replay_limit_cancelled_by_provider() -> None:
    prices = flat("4420.00", 240)  # sopra il BUY LIMIT 4415.31: mai eseguito
    result = run_replay(
        [msg(SAMPLES["limit_exact"], 10, 60),
         msg(SAMPLES["cancelled"], 11, 120, reply_to_msg_id=10)],
        series(prices), cfg(), server_offset_hours=3,
    )  # fmt: skip
    assert result.decisions[("CANCEL", "OK")] == 1
    assert result.trades[10].outcome is Outcome.NOT_FILLED
    assert result.trades[10].exit_at == START + timedelta(minutes=120, seconds=1)


def test_replay_respects_max_open_positions() -> None:
    texts = [
        SAMPLES["limit_exact"],
        SAMPLES["limit_exact"].replace("ENTRY: 4415.31", "ENTRY: 4416.31"),
        SAMPLES["limit_exact"].replace("ENTRY: 4415.31", "ENTRY: 4416.81"),
    ]
    result = run_replay(
        [msg(t, 20 + i, 60 + i) for i, t in enumerate(texts)],
        series(flat("4420.00", 240)), cfg(max_open_positions=2), server_offset_hours=3,
    )  # fmt: skip
    assert result.decisions[("OPEN_PENDING", "OK")] == 2
    assert result.decisions[(Action.REJECT.value, Reason.F11.value)] == 1


def test_replay_skips_signal_when_market_closed() -> None:
    result = run_replay([msg(SAMPLES["plain_range"], 1, 600)], series(flat("4314", 60)), cfg(),
                        server_offset_hours=3)  # fmt: skip
    assert result.decisions[("REJECT", "S7")] == 1


# --- export MT5 (conversione, senza MetaTrader5) ------------------------------------------------


def test_rates_conversion_to_utc_and_spread_in_price() -> None:
    server_epoch = int(datetime(2026, 10, 6, 14, 0, tzinfo=UTC).timestamp())  # ora server
    rows = rates_to_rows(
        [{"time": server_epoch, "open": 4314.0, "high": 4315.1, "low": 4313.0,
          "close": 4314.55, "spread": 25}],
        point=0.01, digits=2, offset_hours=3,
    )  # fmt: skip
    assert rows == [{
        "time_utc": "2026-10-06T11:00:00+00:00", "open": "4314.00", "high": "4315.10",
        "low": "4313.00", "close": "4314.55", "spread": "0.25",
    }]  # fmt: skip


def test_server_offset_estimate() -> None:
    now = datetime(2026, 10, 6, 11, 0, 7, tzinfo=UTC).timestamp()
    tick = int(now + 3 * 3600 - 5)
    assert estimate_server_offset_hours(tick, now) == 3
