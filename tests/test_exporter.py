"""Test dell'exporter con veri oggetti TL di Telethon e un client finto in sola lettura."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from telethon.tl.types import (
    Document,
    Message,
    MessageActionPinMessage,
    MessageFwdHeader,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageReplyHeader,
    MessageService,
    PeerChannel,
)

from momentum_master.exporter.export import export_channel, message_to_record, read_jsonl
from momentum_master.exporter.models import ExportedMessage
from momentum_master.exporter.stats import summarize

CHANNEL_ID = 1234567890
T0 = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


def make_msg(msg_id: int, text: str = "", **kwargs: Any) -> Message:
    return Message(
        id=msg_id,
        peer_id=PeerChannel(CHANNEL_ID),
        date=kwargs.pop("date", T0 + timedelta(minutes=msg_id)),
        message=text,
        **kwargs,
    )


# --- conversione di un messaggio --------------------------------------------------


def test_plain_text_message() -> None:
    rec = message_to_record(make_msg(10, "XAUUSD BUY 2650"), CHANNEL_ID, NOW)
    assert rec.msg_id == 10
    assert rec.text == "XAUUSD BUY 2650"
    assert rec.date_utc == T0 + timedelta(minutes=10)
    assert rec.reply_to_msg_id is None
    assert not rec.is_forward and not rec.is_service and not rec.is_media_only


def test_reply_edit_and_quote_are_kept() -> None:
    msg = make_msg(
        11,
        "SL 2642",
        reply_to=MessageReplyHeader(reply_to_msg_id=10, quote_text="BUY 2650"),
        edit_date=T0 + timedelta(hours=1),
    )
    rec = message_to_record(msg, CHANNEL_ID, NOW)
    assert rec.reply_to_msg_id == 10
    assert rec.reply_quote_text == "BUY 2650"
    assert rec.edit_date_utc == T0 + timedelta(hours=1)


def test_screenshot_without_text_is_media_only() -> None:
    rec = message_to_record(make_msg(12, "", media=MessageMediaPhoto()), CHANNEL_ID, NOW)
    assert rec.media_type == "MessageMediaPhoto"
    assert rec.is_media_only


def test_document_mime_type() -> None:
    doc = Document(
        id=1,
        access_hash=2,
        file_reference=b"",
        date=T0,
        mime_type="video/mp4",
        size=10,
        dc_id=1,
        attributes=[],
    )
    rec = message_to_record(
        make_msg(13, "guarda", media=MessageMediaDocument(document=doc)), CHANNEL_ID, NOW
    )
    assert rec.media_mime_type == "video/mp4"
    assert not rec.is_media_only


def test_forward_and_author() -> None:
    msg = make_msg(14, "copy", fwd_from=MessageFwdHeader(date=T0), post_author="Admin")
    rec = message_to_record(msg, CHANNEL_ID, NOW)
    assert rec.is_forward
    assert rec.post_author == "Admin"


def test_service_message() -> None:
    msg = MessageService(
        id=15,
        peer_id=PeerChannel(CHANNEL_ID),
        date=T0,
        action=MessageActionPinMessage(),
    )
    rec = message_to_record(msg, CHANNEL_ID, NOW)
    assert rec.is_service
    assert rec.service_action == "MessageActionPinMessage"
    assert rec.text == ""


def test_non_utc_dates_are_converted() -> None:
    rome = timezone(timedelta(hours=2))
    msg = make_msg(16, "x", date=datetime(2026, 9, 1, 10, 0, tzinfo=rome))
    rec = message_to_record(msg, CHANNEL_ID, NOW)
    assert rec.date_utc == datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def test_naive_date_is_rejected() -> None:
    with pytest.raises(ValueError):
        message_to_record(make_msg(17, "x", date=datetime(2026, 9, 1)), CHANNEL_ID, NOW)  # noqa: DTZ001


def test_model_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        ExportedMessage(channel_id=1, msg_id=1, date_utc=T0, exported_at_utc=NOW, unexpected="x")


# --- esportazione completa ----------------------------------------------------------


class FakeReadOnlyClient:
    """Espone solo get_entity e iter_messages: qualsiasi altra chiamata fa fallire il test."""

    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages
        self.calls: list[dict[str, Any]] = []

    async def get_entity(self, entity: Any) -> Any:
        return SimpleNamespace(id=CHANNEL_ID)

    def iter_messages(self, entity: Any, limit: int | None = None, **kwargs: Any) -> Any:
        self.calls.append({"limit": limit, **kwargs})
        min_id = kwargs.get("min_id", 0)
        selected = sorted((m for m in self._messages if m.id > min_id), key=lambda m: m.id)
        if limit is not None:
            selected = selected[:limit]

        async def gen() -> Any:
            for m in selected:
                yield m

        return gen()

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"l'exporter non deve chiamare {name}: deve restare in sola lettura")


async def test_export_writes_jsonl_oldest_first(tmp_path: Path) -> None:
    out = tmp_path / "storico.jsonl"
    client = FakeReadOnlyClient([make_msg(3, "c"), make_msg(1, "a"), make_msg(2, "b")])

    result = await export_channel(client, "@canale", out)

    assert result.new_messages == 3
    assert [r.msg_id for r in read_jsonl(out)] == [1, 2, 3]
    assert client.calls[0]["reverse"] is True
    assert not (tmp_path / "storico.jsonl.part").exists()


async def test_export_resumes_from_last_id(tmp_path: Path) -> None:
    out = tmp_path / "storico.jsonl"
    await export_channel(FakeReadOnlyClient([make_msg(1, "a"), make_msg(2, "b")]), 1, out)

    client = FakeReadOnlyClient([make_msg(1, "a"), make_msg(2, "b"), make_msg(3, "c")])
    result = await export_channel(client, 1, out)

    assert result.resumed_from_msg_id == 2
    assert result.new_messages == 1
    assert client.calls[0]["min_id"] == 2
    assert [r.msg_id for r in read_jsonl(out)] == [1, 2, 3]


async def test_interrupted_export_leaves_main_file_intact(tmp_path: Path) -> None:
    out = tmp_path / "storico.jsonl"
    await export_channel(FakeReadOnlyClient([make_msg(1, "a")]), 1, out)
    before = out.read_text(encoding="utf-8")

    class Exploding(FakeReadOnlyClient):
        def iter_messages(self, entity: Any, limit: int | None = None, **kwargs: Any) -> Any:
            async def gen() -> Any:
                yield make_msg(2, "b")
                raise ConnectionError("rete persa")

            return gen()

    with pytest.raises(ConnectionError):
        await export_channel(Exploding([]), 1, out)

    assert out.read_text(encoding="utf-8") == before
    # Al giro successivo il .part viene sovrascritto e l'esportazione riprende pulita.
    result = await export_channel(FakeReadOnlyClient([make_msg(1), make_msg(2, "b")]), 1, out)
    assert result.new_messages == 1
    assert [r.msg_id for r in read_jsonl(out)] == [1, 2]


async def test_no_resume_refuses_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "storico.jsonl"
    await export_channel(FakeReadOnlyClient([make_msg(1, "a")]), 1, out)
    with pytest.raises(FileExistsError):
        await export_channel(FakeReadOnlyClient([make_msg(2)]), 1, out, resume=False)


def test_read_jsonl_reports_bad_line(tmp_path: Path) -> None:
    out = tmp_path / "rotto.jsonl"
    out.write_text('{"non": "valido"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"rotto\.jsonl:1"):
        list(read_jsonl(out))


# --- riepilogo ----------------------------------------------------------------------


def test_summary_counts() -> None:
    records = [
        message_to_record(make_msg(1, "BUY"), CHANNEL_ID, NOW),
        message_to_record(
            make_msg(2, "SL", reply_to=MessageReplyHeader(reply_to_msg_id=1)), CHANNEL_ID, NOW
        ),
        message_to_record(make_msg(5, "", media=MessageMediaPhoto()), CHANNEL_ID, NOW),
    ]
    summary = summarize(records)
    assert summary["total"] == 3
    assert summary["replies"] == 1
    assert summary["media_only"] == 1
    assert summary["id_gaps_estimate"] == 2  # id 3 e 4 mancanti
    assert summarize([]) == {"total": 0}
