"""Test dell'esplorazione. I testi qui sono SINTETICI: non rappresentano il formato di WDT."""

from datetime import UTC, datetime, timedelta

from momentum_master.analysis.explore import build_report, message_shape
from momentum_master.exporter.models import ExportedMessage

T0 = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def rec(msg_id: int, text: str, **kwargs: object) -> ExportedMessage:
    return ExportedMessage(
        channel_id=1,
        msg_id=msg_id,
        date_utc=kwargs.pop("date_utc", T0 + timedelta(minutes=msg_id)),
        text=text,
        exported_at_utc=T0 + timedelta(days=30),
        **kwargs,
    )


def test_shape_replaces_numbers_and_joins_lines() -> None:
    assert message_shape("🟢 BUY 2650-2647\nSL 2642") == ("emoji_large_green_circle buy N-N / sl N")


def test_same_shape_for_different_prices() -> None:
    assert message_shape("SELL 2661,5 SL 2669") == message_shape("SELL 2700.0 SL 2710")


def test_report_groups_counts_and_replies() -> None:
    messages = [
        rec(1, "BUY 2650 SL 2642 TP 2655"),
        rec(2, "BUY 2660 SL 2652 TP 2665"),
        rec(3, "SL 2650", reply_to_msg_id=1),
        rec(4, "promo", edit_date_utc=T0 + timedelta(minutes=10)),
        rec(5, "risposta a messaggio sparito", reply_to_msg_id=999),
        rec(6, "", media_type="MessageMediaPhoto"),
    ]
    report = build_report(messages)

    assert "Messaggi con testo: **5**" in report
    assert "| 1 | 2 | 40.0 | `buy N sl N tp N` | 1, 2 |" in report
    assert "Messaggi in risposta: 2" in report
    assert "Risposte a messaggi non presenti (cancellati?): 1" in report
    assert "mediana 2.0 min" in report  # risposta 3 → 1: 2 minuti
    assert "Messaggi modificati: 1" in report
    assert "Solo media senza testo: 1" in report
    assert "| buy | 2 | 40.0 |" in report


def test_report_flags_ambiguous_numbers() -> None:
    report = build_report([rec(7, "TP 2,655")])
    assert "Messaggi con numeri ambigui o non validi: 1 (primi id: 7)" in report


def test_empty_report() -> None:
    assert "Nessun messaggio con testo." in build_report([])
