"""Config: il file reale si carica; gli errori pericolosi bloccano l'avvio."""

from __future__ import annotations

import copy
from datetime import time
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from momentum_master.config import ConfigError, Mode, load_config, parse_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
BASE = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def variant(**changes: object) -> dict:
    """Copia del config reale con modifiche puntuali, es. variant(**{"mode": "demo"})."""
    data = copy.deepcopy(BASE)
    for dotted, value in changes.items():
        node = data
        *parents, leaf = dotted.split("__")
        for key in parents:
            node = node[key]
        node[leaf] = value
    return data


def ready_for_demo() -> dict:
    return variant(
        mode="demo",
        filters__confirmed=True,
        filters__confirmed_on="2026-11-01",
        telegram__channel_poster_ids=[777],
        telegram__group_id=-1001,
        telegram__admin_chat_id=-1002,
        telegram__admin_ids=[42],
        mt5__symbol="XAUUSD",
        mt5__server="FPG-Demo",
        mt5__terminal_path="C:/mt5/terminal64.exe",
    )


def test_real_config_file_loads_in_paper() -> None:
    cfg = load_config(CONFIG_PATH)
    assert cfg.mode is Mode.PAPER
    assert not cfg.filters.confirmed
    assert cfg.targets.tp_index == 1 and cfg.targets.be_after_tp is None  # D5
    assert cfg.filters.range_entry_tolerance == 0  # D2
    assert cfg.pending.heads_up_policy == "notify_only"  # D4
    assert cfg.safety.rollover_window.start == time(23, 50)
    assert cfg.safety.spread_emergency == Decimal("1.50")


@pytest.mark.parametrize("mode", ["demo", "live"])
def test_cannot_leave_paper_without_confirmed_filters(mode: str) -> None:
    with pytest.raises(ConfigError, match=r"filters\.confirmed"):
        parse_config(variant(mode=mode))


def test_demo_allowed_only_when_everything_is_set() -> None:
    assert parse_config(ready_for_demo()).mode is Mode.DEMO


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("telegram__channel_poster_ids", None),
        ("telegram__channel_poster_ids", []),
        ("mt5__symbol", None),
        ("telegram__admin_ids", []),
    ],
)
def test_demo_requires_fpg_and_telegram_data(field: str, value: object) -> None:
    data = ready_for_demo()
    *parents, leaf = field.split("__")
    data[parents[0]][leaf] = value
    with pytest.raises(ConfigError, match="mode = demo non consentito"):
        parse_config(data)


def test_confirmed_filters_need_a_date() -> None:
    with pytest.raises(ConfigError, match="confirmed_on"):
        parse_config(variant(filters__confirmed=True))


def test_typo_in_key_is_rejected() -> None:
    data = variant()
    data["filters"]["max_spred"] = 0.3  # errore di battitura
    with pytest.raises(ConfigError, match="max_spred"):
        parse_config(data)


@pytest.mark.parametrize("secret", ["password", "api_hash", "bot_token"])
def test_secrets_are_not_accepted_in_config(secret: str) -> None:
    data = variant()
    data["mt5"][secret] = "xxx"
    with pytest.raises(ConfigError):
        parse_config(data)


def test_unquoted_time_is_rejected_not_misread() -> None:
    raw = CONFIG_PATH.read_text(encoding="utf-8").replace('start: "23:50"', "start: 23:50")
    with pytest.raises(ConfigError, match="virgolette"):
        parse_config(yaml.safe_load(raw))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("targets__tp_index", 0),
        ("targets__tp_index", 6),
        ("safety__max_signal_age_s", 0),
        ("safety__spread_emergency", 0),
        ("sizing__master_lot", 2),  # oltre max_lot 1.00
        ("mode", "turbo"),
        ("filters__order_type_mode", "tutto"),
    ],
)
def test_out_of_range_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ConfigError):
        parse_config(variant(**{field: value}))


def test_missing_file_and_bad_yaml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="non trovato"):
        load_config(tmp_path / "manca.yaml")
    bad = tmp_path / "rotto.yaml"
    bad.write_text("mode: [paper\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML non valido"):
        load_config(bad)
    lista = tmp_path / "lista.yaml"
    lista.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mappa"):
        load_config(lista)


def test_error_message_lists_the_field() -> None:
    with pytest.raises(ConfigError) as info:
        parse_config(variant(targets__tp_index=9))
    assert "targets.tp_index" in str(info.value)
    assert "il bot non parte" in str(info.value)
