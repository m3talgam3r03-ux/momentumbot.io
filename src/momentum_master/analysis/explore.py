"""Esplorazione dello storico esportato: base per scrivere catalogo_formati.md (passo 2).

NON classifica e NON assume nessun formato. Raggruppa i messaggi per "forma"
(testo normalizzato con i numeri sostituiti da ``N``) e conta parole, emoji,
risposte, modifiche e grandezza dei numeri. Il catalogo lo si scrive leggendo
questo rapporto e i messaggi reali, non indovinando.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import timedelta
from decimal import Decimal

from momentum_master.classifier.normalize import EMOJI_TOKEN_PREFIX, normalize_text
from momentum_master.classifier.numbers import extract_numbers
from momentum_master.exporter.models import ExportedMessage

# Parole cercate per contarne la presenza. IPOTESI: sono parole comuni nei canali di
# segnali sull'oro; il rapporto dice quante volte compaiono DAVVERO su WDT MOMENTUM.
CANDIDATE_KEYWORDS: tuple[str, ...] = (
    "buy", "sell", "long", "short", "now", "limit", "stop", "entry", "zone",
    "sl", "tp", "tp1", "tp2", "tp3", "open", "pips", "pip", "points", "hit",
    "close", "closed", "partial", "be", "breakeven", "cancel", "cancelled",
    "again", "add", "risky", "risk", "gold", "xau", "xauusd", "oro",
)  # fmt: skip

# L'underscore tiene uniti i token emoji (EMOJI_LARGE_GREEN_CIRCLE).
_WORD = re.compile(r"[a-zà-ÿ][a-zà-ÿ0-9_]*", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def message_shape(text: str) -> str:
    """Forma del messaggio: normalizzato, minuscolo, numeri → N, una riga sola.

    "🟢 BUY 2650-2647\\nSL 2642" → "emoji_large_green_circle buy N-N / sl N"
    """
    normalized = normalize_text(text)
    pieces: list[str] = []
    last = 0
    for token in extract_numbers(normalized):
        pieces.append(normalized[last : token.start].casefold())
        pieces.append("N")
        last = token.end
    pieces.append(normalized[last:].casefold())
    shaped = "".join(pieces)
    lines = [_SPACES.sub(" ", line).strip() for line in shaped.split("\n")]
    return " / ".join(line for line in lines if line)


def _words(normalized: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(normalized)]


def _magnitude(value: Decimal) -> str:
    if value < 100:
        return "< 100 (pips? punti? etichette?)"
    if value < 1000:
        return "100 - 999 (pips? prezzi abbreviati?)"
    return ">= 1000 (prezzi?)"


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def _fmt_minutes(values: Sequence[float]) -> str:
    if not values:
        return "n/d"
    return (
        f"mediana {statistics.median(values):.1f} min, "
        f"95° percentile {_percentile(values, 0.95):.1f} min, max {max(values):.1f} min"
    )


def _excerpt(text: str, limit: int = 300) -> str:
    flat = text.replace("\n", " ⏎ ").replace("|", "¦")
    return flat if len(flat) <= limit else flat[:limit] + "…"


def build_report(messages: Iterable[ExportedMessage], *, top_shapes: int = 40) -> str:
    """Rapporto Markdown in italiano sullo storico."""
    items = sorted((m for m in messages if not m.is_service), key=lambda m: m.msg_id)
    with_text = [m for m in items if m.text.strip()]
    by_id = {m.msg_id: m for m in items}
    out: list[str] = ["# Esplorazione dello storico (base per catalogo_formati.md)", ""]
    if not with_text:
        out.append("Nessun messaggio con testo.")
        return "\n".join(out)

    total = len(with_text)
    out += [
        f"- Messaggi con testo: **{total}** (su {len(items)} non di servizio)",
        f"- Periodo UTC: {items[0].date_utc:%Y-%m-%d %H:%M} → {items[-1].date_utc:%Y-%m-%d %H:%M}",
        f"- Solo media senza testo: {sum(1 for m in items if m.is_media_only)}",
        "",
    ]

    # Forme ricorrenti
    groups: dict[str, list[ExportedMessage]] = defaultdict(list)
    for m in with_text:
        groups[message_shape(m.text)].append(m)
    ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0].msg_id))
    out += [
        f"## Forme più frequenti (prime {top_shapes} su {len(groups)} distinte)",
        "",
        "| # | Messaggi | % | Forma | Esempi (msg_id) |",
        "|---|---|---|---|---|",
    ]
    for rank, (shape, members) in enumerate(ranked[:top_shapes], start=1):
        ids = ", ".join(str(m.msg_id) for m in members[:3])
        pct = 100 * len(members) / total
        out.append(f"| {rank} | {len(members)} | {pct:.1f} | `{_excerpt(shape, 160)}` | {ids} |")
    singletons = sum(1 for members in groups.values() if len(members) == 1)
    out += ["", f"Forme che compaiono una sola volta: {singletons}", ""]

    # Parole ed emoji
    words: Counter[str] = Counter()
    emojis: Counter[str] = Counter()
    presence: Counter[str] = Counter()
    for m in with_text:
        tokens = _words(normalize_text(m.text))
        for tok in tokens:
            if tok.startswith(EMOJI_TOKEN_PREFIX.casefold()):
                emojis[tok] += 1
            else:
                words[tok] += 1
        presence.update(set(tokens) & set(CANDIDATE_KEYWORDS))

    out += ["## Parole cercate (IPOTESI da verificare): in quanti messaggi compaiono", ""]
    out += ["| Parola | Messaggi | % |", "|---|---|---|"]
    for kw in CANDIDATE_KEYWORDS:
        out.append(f"| {kw} | {presence[kw]} | {100 * presence[kw] / total:.1f} |")
    out += ["", "## Parole più frequenti (prime 60)", ""]
    out.append(", ".join(f"{w} ({c})" for w, c in words.most_common(60)))
    out += ["", "## Emoji più frequenti (prime 30)", ""]
    out.append(", ".join(f"{e} ({c})" for e, c in emojis.most_common(30)) or "nessuna")
    out.append("")

    # Numeri
    magnitudes: Counter[str] = Counter()
    ambiguous_ids: list[int] = []
    for m in with_text:
        tokens = extract_numbers(normalize_text(m.text))
        if any(t.is_ambiguous or not t.is_valid for t in tokens):
            ambiguous_ids.append(m.msg_id)
        for t in tokens:
            if t.value is not None:
                magnitudes[_magnitude(t.value)] += 1
    out += ["## Numeri", "", "| Grandezza | Occorrenze |", "|---|---|"]
    for label, count in sorted(magnitudes.items()):
        out.append(f"| {label} | {count} |")
    out += [
        "",
        f"Messaggi con numeri ambigui o non validi: {len(ambiguous_ids)}"
        + (f" (primi id: {', '.join(map(str, ambiguous_ids[:20]))})" if ambiguous_ids else ""),
        "",
    ]

    # Risposte
    replies = [m for m in with_text if m.reply_to_msg_id is not None]
    reply_delays = [
        (m.date_utc - by_id[m.reply_to_msg_id].date_utc) / timedelta(minutes=1)
        for m in replies
        if m.reply_to_msg_id in by_id
    ]
    orphan = sum(1 for m in replies if m.reply_to_msg_id not in by_id)
    reply_shapes = Counter(message_shape(m.text) for m in replies)
    out += [
        "## Risposte (come il canale collega gli aggiornamenti)",
        "",
        f"- Messaggi in risposta: {len(replies)} ({100 * len(replies) / total:.1f}%)",
        f"- Risposte a messaggi non presenti (cancellati?): {orphan}",
        f"- Ritardo dal messaggio originale: {_fmt_minutes(reply_delays)}",
        "",
        "| Messaggi | Forma della risposta |",
        "|---|---|",
    ]
    for shape, count in reply_shapes.most_common(20):
        out.append(f"| {count} | `{_excerpt(shape, 160)}` |")
    out.append("")

    # Modifiche
    edited = [m for m in with_text if m.edit_date_utc is not None]
    edit_delays = [(m.edit_date_utc - m.date_utc) / timedelta(minutes=1) for m in edited]
    out += [
        "## Modifiche",
        "",
        f"- Messaggi modificati: {len(edited)} ({100 * len(edited) / total:.1f}%)",
        f"- Ritardo della modifica: {_fmt_minutes(edit_delays)}",
        "- Attenzione: l'export vede solo il testo FINALE dei messaggi modificati.",
        "",
    ]

    # Orari
    hours = Counter(m.date_utc.hour for m in with_text)
    out += ["## Messaggi per ora (UTC)", "", "| Ora | Messaggi |", "|---|---|"]
    out += [f"| {h:02d} | {hours[h]} |" for h in range(24) if hours[h]]
    out.append("")

    # Esempi per le prime forme
    out += ["## Esempi reali delle prime 15 forme", ""]
    for rank, (shape, members) in enumerate(ranked[:15], start=1):
        out.append(f"### {rank}. `{_excerpt(shape, 120)}` ({len(members)} messaggi)")
        out.append("")
        for m in members[:3]:
            out.append(f"- **{m.msg_id}** ({m.date_utc:%Y-%m-%d %H:%M} UTC): {_excerpt(m.text)}")
        out.append("")
    return "\n".join(out)
