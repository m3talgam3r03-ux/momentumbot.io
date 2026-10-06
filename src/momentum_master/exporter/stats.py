"""Riepilogo statistico di un'esportazione: serve a pianificare il catalogo dei formati.

Non classifica nulla: conta soltanto ciò che è oggettivo (testo, media, risposte, modifiche).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from momentum_master.exporter.models import ExportedMessage


def summarize(messages: Iterable[ExportedMessage]) -> dict[str, Any]:
    """Restituisce i conteggi principali dello storico esportato."""
    items = sorted(messages, key=lambda m: m.msg_id)
    if not items:
        return {"total": 0}

    per_day = Counter(m.date_utc.date().isoformat() for m in items if not m.is_service)
    authors = Counter(m.post_author or "(nessuna firma)" for m in items if not m.is_service)
    media = Counter(m.media_type for m in items if m.media_type)
    services = Counter(m.service_action for m in items if m.is_service)
    ids = [m.msg_id for m in items]

    return {
        "total": len(items),
        "first_date_utc": items[0].date_utc.isoformat(),
        "last_date_utc": items[-1].date_utc.isoformat(),
        "days_with_messages": len(per_day),
        "with_text": sum(1 for m in items if m.text.strip()),
        "media_only": sum(1 for m in items if m.is_media_only),
        "replies": sum(1 for m in items if m.reply_to_msg_id is not None),
        "edited": sum(1 for m in items if m.edit_date_utc is not None),
        "forwarded": sum(1 for m in items if m.is_forward),
        "service": sum(1 for m in items if m.is_service),
        "albums": len({m.grouped_id for m in items if m.grouped_id is not None}),
        # Buchi negli id = messaggi cancellati (o di servizio non restituiti): stima, non certezza.
        "id_gaps_estimate": (ids[-1] - ids[0] + 1) - len(ids),
        "max_messages_per_day": max(per_day.values(), default=0),
        "post_authors": dict(authors.most_common()),
        "media_types": dict(media.most_common()),
        "service_actions": dict(services.most_common()),
    }


def format_summary(summary: dict[str, Any]) -> str:
    """Testo leggibile in italiano del riepilogo."""
    if summary.get("total", 0) == 0:
        return "Nessun messaggio esportato."
    lines = [
        f"Messaggi totali:           {summary['total']}",
        f"Periodo (UTC):             {summary['first_date_utc']} → {summary['last_date_utc']}",
        f"Giorni con messaggi:       {summary['days_with_messages']}",
        f"Con testo:                 {summary['with_text']}",
        f"Solo media (no testo):     {summary['media_only']}",
        f"Risposte (reply):          {summary['replies']}",
        f"Modificati:                {summary['edited']}",
        f"Inoltrati:                 {summary['forwarded']}",
        f"Di servizio:               {summary['service']}",
        f"Album:                     {summary['albums']}",
        f"Id mancanti (stima canc.): {summary['id_gaps_estimate']}",
        f"Max messaggi in un giorno: {summary['max_messages_per_day']}",
        f"Firme autori:              {summary['post_authors']}",
        f"Tipi di media:             {summary['media_types']}",
    ]
    return "\n".join(lines)
