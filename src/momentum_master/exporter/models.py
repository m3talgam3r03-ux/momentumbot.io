"""Modello di un messaggio esportato dallo storico del canale (una riga JSONL)."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, field_validator

SCHEMA_VERSION = 1


class ExportedMessage(BaseModel):
    """Un messaggio del canale così come Telegram lo restituisce oggi.

    Il testo è salvato INVARIATO (``message.message`` di Telethon: testo senza markup;
    la formattazione sta nelle entities, che non esportiamo). La normalizzazione avviene
    dopo, in ``classifier.normalize``, senza mai sovrascrivere questo campo.

    Limite noto: l'esportazione vede solo la versione FINALE di un messaggio modificato
    (``edit_date_utc`` dice solo che è stato modificato) e non vede i messaggi cancellati.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    channel_id: int
    msg_id: int
    date_utc: datetime
    edit_date_utc: datetime | None = None
    text: str = ""
    reply_to_msg_id: int | None = None
    reply_quote_text: str | None = None
    media_type: str | None = None
    media_mime_type: str | None = None
    grouped_id: int | None = None
    is_forward: bool = False
    post_author: str | None = None
    is_service: bool = False
    service_action: str | None = None
    exported_at_utc: datetime

    @field_validator("date_utc", "edit_date_utc", "exported_at_utc")
    @classmethod
    def _must_be_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("le date devono essere timezone-aware in UTC")
        return value

    @property
    def is_media_only(self) -> bool:
        """Messaggio con media e senza testo (es. screenshot): mai eseguibile."""
        return self.media_type is not None and not self.text.strip()
