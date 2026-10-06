"""Testi ESATTI dall'export di Telegram Desktop del 2026-10-06 (gruppo WDT MOMENTUM).

Sostituiscono le trascrizioni da screenshot dove serve il carattere esatto (apostrofo ’,
"%0A" e "\\n" scritti letteralmente, varianti di formato).
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

from momentum_master.classifier.classify import classify
from momentum_master.classifier.models import Category
from momentum_master.exporter.models import ExportedMessage
from test_reading_safety import _check_literal_reading, _random_mutation

SAMPLES = json.loads(
    (Path(__file__).parent / "data" / "wdt_real_samples.json").read_text(encoding="utf-8")
)
T0 = datetime(2026, 10, 6, tzinfo=UTC)


def run(key: str):
    return classify(
        ExportedMessage(channel_id=1, msg_id=1, date_utc=T0, text=SAMPLES[key], exported_at_utc=T0)
    )


@pytest.mark.parametrize(
    ("key", "side", "hint", "entry", "sl", "tp1"),
    [
        ("plain_range", "SELL", "MARKET", ("4313.68", "4314.68"), "4322.68", "4309.08"),
        ("literal_backslash_n", "SELL", "MARKET", ("4321.58", "4322.58"), "4330.58", "4316.98"),
        ("percent0a", "BUY", "MARKET", ("4291.70", "4292.70"), "4283.70", "4297.30"),
        ("limit_exact", "BUY", "LIMIT", ("4415.31", "4415.31"), "4410.31", "4417.81"),
    ],
)
def test_real_openings(key: str, side: str, hint: str, entry: tuple, sl: str, tp1: str) -> None:
    c = run(key)
    assert c.category is Category.NEW_SIGNAL_COMPLETE, c.notes
    assert (c.side, c.order_hint) == (side, hint)
    assert (c.entry_min, c.entry_max) == (D(entry[0]), D(entry[1]))
    assert (c.sl, c.tps[0]) == (D(sl), D(tp1))


def test_wide_range_917_is_held_back() -> None:
    # Segnale vero, ma range largo 6 (limite 3,00): AMBIGUOUS, decisione di Lorenzo.
    c = run("wide_range_917")
    assert c.category is Category.AMBIGUOUS
    assert "range largo 6" in c.notes


def test_manual_signal_1128_is_not_executed() -> None:
    assert run("manual_buy_xau_1128").category is Category.AMBIGUOUS


@pytest.mark.parametrize("key", ["preparati", "prep_old", "out_of_trade", "heads_up", "cancelled"])
def test_real_non_openings(key: str) -> None:
    assert run(key).category is not Category.NEW_SIGNAL_COMPLETE


@pytest.mark.parametrize("key", ["plain_range", "literal_backslash_n", "percent0a", "limit_exact"])
def test_fuzz_real_texts(key: str) -> None:
    rng = random.Random(f"real-{key}")
    for _ in range(300):
        text = SAMPLES[key]
        for _ in range(rng.randint(1, 4)):
            text = _random_mutation(text, rng)
        _check_literal_reading(key, text)
