"""Classificatore: ExportedMessage → ClassifiedMessage.

Stato: riconosce SOLO i messaggi di apertura nei formati catalogati (F-LIMIT, F-RANGE).
Tutto il resto finisce in AMBIGUOUS con il motivo, NON in NOISE: finché un formato non è
catalogato non sappiamo se è rumore o un aggiornamento (es. una chiusura).
Le categorie di aggiornamento/chiusura verranno aggiunte dopo l'export dello storico.

Mittente (decisione di Lorenzo, 2026-10-06, D1): WDT MOMENTUM è un GRUPPO, quindi
chiunque vi scriva può produrre un testo con la forma di un segnale. Con
``authorized_sender_ids`` vengono considerati solo i messaggi degli account autorizzati
(config: ``telegram.channel_poster_ids``). Se un amministratore pubblica in modo anonimo
come il gruppo, il suo ``sender_id`` è l'id del gruppo stesso: in quel caso va autorizzato
anche quello. Gli id reali si leggono dall'export (campo ``sender_id``).
``None`` = nessun filtro (solo per l'analisi dello storico, mai in esercizio).

Funzione pura: nessun I/O, stesso input → stesso output.
"""

from __future__ import annotations

from momentum_master.classifier.models import Category, ClassifiedMessage, Method
from momentum_master.classifier.normalize import normalize_text
from momentum_master.classifier.opening import parse_opening
from momentum_master.exporter.models import ExportedMessage


def classify(
    msg: ExportedMessage, authorized_sender_ids: frozenset[int] | None = None
) -> ClassifiedMessage:
    base = {
        "msg_id": msg.msg_id,
        "date_utc": msg.date_utc,
        "edited": msg.edit_date_utc is not None,
        "raw_text": msg.text,
        "method": Method.REGEX,
    }

    if authorized_sender_ids is not None and msg.sender_id not in authorized_sender_ids:
        return ClassifiedMessage(
            **base,
            category=Category.NOISE,
            confidence=1.0,
            notes=f"mittente non autorizzato: {msg.sender_id}",
        )
    if msg.is_service:
        return ClassifiedMessage(
            **base, category=Category.NOISE, confidence=1.0, notes="messaggio di servizio"
        )
    if msg.is_media_only:
        return ClassifiedMessage(
            **base,
            category=Category.AMBIGUOUS,
            confidence=0.0,
            notes="solo immagine/media senza testo: mai eseguibile (nessun OCR)",
        )

    parsed = parse_opening(normalize_text(msg.text))
    if parsed.ok:
        return ClassifiedMessage(
            **base,
            category=Category.NEW_SIGNAL_COMPLETE,
            side=parsed.side,
            order_hint=parsed.order_hint,
            entry_min=parsed.entry_min,
            entry_max=parsed.entry_max,
            sl=parsed.sl,
            tps=list(parsed.tps),
            tp_open=parsed.tp_open,
            confidence=1.0,
            notes=f"formato {parsed.format_id}",
        )
    if parsed.looks_like_opening:
        return ClassifiedMessage(
            **base,
            category=Category.AMBIGUOUS,
            side=parsed.side,
            confidence=0.3,
            notes=f"sembra un'apertura {parsed.format_id} ma: " + "; ".join(parsed.problems),
        )
    return ClassifiedMessage(
        **base, category=Category.AMBIGUOUS, confidence=0.0, notes="formato non ancora catalogato"
    )
