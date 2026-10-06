"""Esportazione in sola lettura dello storico del canale in JSONL.

Usa da Telethon SOLO ``get_entity`` e ``iter_messages``: nessuna scrittura sul canale,
nessuna conferma di lettura, nessuna iscrizione.

Scrittura sicura: i nuovi messaggi vanno prima in ``<file>.part``; solo a esportazione
completata vengono aggiunti al file principale. Un'interruzione non lascia righe a metà.
Ripresa: con ``resume=True`` si scaricano solo i messaggi con id maggiore dell'ultimo salvato.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from momentum_master.exporter.models import ExportedMessage

logger = logging.getLogger(__name__)


class ReadOnlyTelegramClient(Protocol):
    """Sottoinsieme di ``telethon.TelegramClient`` usato dall'exporter."""

    async def get_entity(self, entity: Any) -> Any: ...

    def iter_messages(self, entity: Any, limit: int | None = None, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ExportResult:
    channel_id: int
    out_path: Path
    new_messages: int
    skipped_duplicates: int
    resumed_from_msg_id: int


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # Telethon restituisce date UTC timezone-aware; una data "naive" è un'anomalia.
        raise ValueError(f"data senza fuso orario dal client Telegram: {value!r}")
    return value.astimezone(UTC)


def message_to_record(msg: Any, channel_id: int, exported_at: datetime) -> ExportedMessage:
    """Converte un ``Message``/``MessageService`` di Telethon in ``ExportedMessage``.

    Funzione pura: legge solo attributi, non fa chiamate di rete.
    """
    action = getattr(msg, "action", None)
    media = getattr(msg, "media", None)
    reply_to = getattr(msg, "reply_to", None)
    document = getattr(media, "document", None) if media is not None else None

    return ExportedMessage(
        channel_id=channel_id,
        msg_id=msg.id,
        date_utc=_as_utc(msg.date),
        edit_date_utc=_as_utc(getattr(msg, "edit_date", None)),
        text=getattr(msg, "message", None) or "",
        reply_to_msg_id=getattr(reply_to, "reply_to_msg_id", None),
        reply_quote_text=getattr(reply_to, "quote_text", None),
        media_type=type(media).__name__ if media is not None else None,
        media_mime_type=getattr(document, "mime_type", None),
        grouped_id=getattr(msg, "grouped_id", None),
        is_forward=getattr(msg, "fwd_from", None) is not None,
        post_author=getattr(msg, "post_author", None),
        sender_id=getattr(msg, "sender_id", None),
        is_service=action is not None,
        service_action=type(action).__name__ if action is not None else None,
        exported_at_utc=exported_at.astimezone(UTC),
    )


def read_jsonl(path: Path) -> Iterator[ExportedMessage]:
    """Legge un file JSONL esportato, validando ogni riga. Una riga non valida è un errore."""
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield ExportedMessage.model_validate_json(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_no}: riga non valida: {exc}") from exc


def _existing_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {record.msg_id for record in read_jsonl(path)}


async def export_channel(
    client: ReadOnlyTelegramClient,
    channel: int | str,
    out_path: Path,
    *,
    resume: bool = True,
    limit: int | None = None,
    wait_time: float | None = None,
    progress_every: int = 500,
) -> ExportResult:
    """Esporta i messaggi del canale in ``out_path`` dal più vecchio al più recente.

    Args:
        client: client Telethon già autenticato (sessione utente).
        channel: id numerico (es. -1001234567890) o username del canale.
        out_path: file JSONL di destinazione.
        resume: se True riprende dall'ultimo msg_id già presente nel file.
        limit: numero massimo di messaggi (None = tutti). Utile per una prova.
        wait_time: pausa tra le richieste a Telegram (None = default di Telethon).
        progress_every: ogni quanti messaggi scrivere una riga di avanzamento nel log.
    """
    entity = await client.get_entity(channel)
    channel_id = int(entity.id)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    known_ids = _existing_ids(out_path) if resume else set()
    if not resume and out_path.exists():
        raise FileExistsError(f"{out_path} esiste già: usa resume oppure un altro file")
    min_id = max(known_ids, default=0)

    part_path = out_path.with_name(out_path.name + ".part")
    exported_at = datetime.now(UTC)
    written = 0
    duplicates = 0

    logger.info("Esportazione canale %s da msg_id > %s", channel_id, min_id)
    with part_path.open("w", encoding="utf-8") as part:
        async for msg in client.iter_messages(
            entity, limit=limit, reverse=True, min_id=min_id, wait_time=wait_time
        ):
            if msg.id in known_ids:
                duplicates += 1
                continue
            record = message_to_record(msg, channel_id, exported_at)
            part.write(record.model_dump_json() + "\n")
            known_ids.add(msg.id)
            written += 1
            if written % progress_every == 0:
                logger.info("... %s messaggi esportati (ultimo id %s)", written, msg.id)
        part.flush()
        os.fsync(part.fileno())

    # Accodamento al file principale solo a esportazione completata.
    with part_path.open(encoding="utf-8") as src, out_path.open("a", encoding="utf-8") as dst:
        for line in src:
            dst.write(line)
        dst.flush()
        os.fsync(dst.fileno())
    part_path.unlink()

    logger.info("Esportazione completata: %s nuovi messaggi in %s", written, out_path)
    return ExportResult(
        channel_id=channel_id,
        out_path=out_path,
        new_messages=written,
        skipped_duplicates=duplicates,
        resumed_from_msg_id=min_id,
    )


def dump_json(data: Any, path: Path) -> None:
    """Scrive un JSON leggibile (usato per il riepilogo statistico)."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
