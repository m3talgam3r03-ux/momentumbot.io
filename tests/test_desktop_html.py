"""Lettura dell'export HTML di Telegram Desktop."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from momentum_master.exporter.desktop_html import parse_desktop_date, parse_desktop_html

HTML = """<html><body><div class="history">
<div class="message service" id="message-1"><div class="body details">6 October 2026</div></div>
<div class="message service" id="message1"><div class="body details">
Channel &laquo;SALA 2 (V)&raquo; created
</div></div>
<div class="message default clearfix" id="message2"><div class="body">
<div class="pull_right date details" title="06.10.2026 13:07:21 UTC+02:00">13:07</div>
<div class="from_name">
🌪️MOMENTUM 🌪️
</div>
<div class="text">
❇️ SELL XAUUSD (GOLD) ❇️<br><br>ENTRY RANGE: 4313.68 - 4314.68<br><br>SL ❌: 4322.68<br>TP1✅: 4309.08
</div></div></div>
<div class="message default clearfix joined" id="message3"><div class="body">
<div class="pull_right date details" title="06.10.2026 13:20:00 UTC+02:00">13:20</div>
<div class="reply_to details">In reply to <a href="#go_to_message2">this message</a></div>
<div class="text">
TP1 ✅ HIT<br>Price: 4309.08<br>we&apos;re <strong>in</strong> &amp; out
</div></div></div>
<div class="message default clearfix joined" id="message4"><div class="body">
<div class="pull_right date details" title="06.10.2026 13:21:00 UTC+02:00">13:21</div>
<div class="media_wrap clearfix"><a class="photo_wrap clearfix pull_left" href="photos/p.jpg">
<img class="photo" src="photos/p.jpg"></a></div>
</div></div>
</div></body></html>"""


@pytest.fixture
def parsed(tmp_path: Path):
    path = tmp_path / "messages.html"
    path.write_text(HTML, encoding="utf-8")
    return {m.msg_id: m for m in parse_desktop_html([path])}


def test_date_with_offset_becomes_utc() -> None:
    assert parse_desktop_date("16.09.2026 20:22:05 UTC+01:00") == datetime(
        2026, 9, 16, 19, 22, 5, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        parse_desktop_date("16/09/2026 20:22")


def test_date_separators_are_skipped(parsed) -> None:
    assert -1 not in parsed


def test_signal_text_lines_and_sender(parsed) -> None:
    m = parsed[2]
    assert m.text.split("\n")[:3] == [
        "❇️ SELL XAUUSD (GOLD) ❇️",
        "",
        "ENTRY RANGE: 4313.68 - 4314.68",
    ]
    assert m.post_author == "🌪️MOMENTUM 🌪️"
    assert m.date_utc == datetime(2026, 10, 6, 11, 7, 21, tzinfo=UTC)


def test_joined_message_inherits_sender_and_reply(parsed) -> None:
    m = parsed[3]
    assert m.post_author == "🌪️MOMENTUM 🌪️"
    assert m.reply_to_msg_id == 2
    assert m.text == "TP1 ✅ HIT\nPrice: 4309.08\nwe're in & out"


def test_media_only_message(parsed) -> None:
    assert parsed[4].media_type == "photo" and parsed[4].is_media_only


def test_undated_initial_service_message_is_skipped(parsed) -> None:
    # "Channel created" arriva prima di qualsiasi data: non serve all'analisi, si salta.
    assert 1 not in parsed


def test_command_line_orders_pages(tmp_path: Path) -> None:
    from momentum_master.exporter.desktop_html import main
    from momentum_master.exporter.export import read_jsonl

    (tmp_path / "messages.html").write_text(HTML, encoding="utf-8")
    page2 = HTML.replace('id="message2"', 'id="message10"').replace(
        'id="message3"', 'id="message11"'
    )
    page2 = page2.replace('id="message4"', 'id="message12"').replace(
        'id="message1"', 'id="message9"'
    )
    (tmp_path / "messages2.html").write_text(page2, encoding="utf-8")
    out = tmp_path / "out.jsonl"
    assert main([str(tmp_path), str(out)]) == 0
    ids = [m.msg_id for m in read_jsonl(out)]
    assert ids == sorted(ids) and 12 in ids
    assert main([str(tmp_path / "vuota"), str(out)]) == 1
