"""Rapporto giornaliero dal registro."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from momentum_master.listener.core import ListenerCore
from momentum_master.report import build_daily_report, main
from momentum_master.store import Store
from test_listener import LIMIT_MARKET, SAMPLES, T0, Clock, msg
from test_updates import cfg


def populated(tmp_path: Path) -> Path:
    path = tmp_path / "db.sqlite"
    clock = Clock(T0 + timedelta(seconds=1))
    core = ListenerCore(cfg(), Store(path), market=lambda: LIMIT_MARKET, clock=clock)
    core.on_new_message(msg("limit_exact", 10))
    clock.now = T0 + timedelta(seconds=20)
    core.on_new_message(msg("limit_exact", 11, at=T0 + timedelta(seconds=19)))  # doppione
    clock.now = T0 + timedelta(minutes=5)
    core.on_new_message(msg("rientra_927", 12, at=clock.now))
    clock.now = T0 + timedelta(minutes=60)
    core.on_new_message(msg("cancelled", 13, at=clock.now, reply_to_msg_id=11))
    core.store.close()
    return path


def test_daily_report_contents(tmp_path: Path) -> None:
    report = build_daily_report(populated(tmp_path), date(2026, 10, 6))
    assert "Rapporto del 06/10/2026" in report
    assert "Aperture approvate: **1**" in report
    assert "S11" in report  # il doppione scartato
    assert "msg 13 → CANCEL sul segnale 10" in report
    assert "AMBIGUOUS da rivedere (1)" in report and "RIENTRA" in report
    assert "Mediana 1.00 s" in report


def test_other_day_and_cli(tmp_path: Path, capsys) -> None:
    path = populated(tmp_path)
    assert "Nessun messaggio" in build_daily_report(path, date(2026, 10, 5))
    assert main([str(path), "--giorno", "2026-10-06"]) == 0
    assert "Aperture approvate" in capsys.readouterr().out
    assert main([str(tmp_path / "manca.sqlite")]) == 1


def test_report_does_not_modify_registry(tmp_path: Path) -> None:
    path = populated(tmp_path)
    before = path.stat().st_mtime_ns
    build_daily_report(path, date(2026, 10, 6))
    assert path.stat().st_mtime_ns == before
    assert SAMPLES  # i campioni reali sono disponibili
