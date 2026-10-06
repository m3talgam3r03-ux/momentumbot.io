"""Riconoscimento dei messaggi di APERTURA di WDT MOMENTUM.

Formati osservati su 8 messaggi reali (2026-10-06, vedi docs/catalogo_formati.md):

  F-LIMIT  intestazione "LIMIT ORDER — BUY|SELL XAUUSD (GOLD)", riga "ENTRY: <prezzo>"
  F-RANGE  intestazione "BUY|SELL XAUUSD (GOLD)", riga con "ENTRY RANGE:: <min> - <max>"
  entrambi: "SL ...: <prezzo>", righe "TP<n> ...: <prezzo>" (TP5 può essere "OPEN").

Principio: si riconosce SOLO ciò che corrisponde esattamente a un formato catalogato.
Qualsiasi deviazione (campo mancante, doppio, numero ambiguo, TP non in ordine) →
nessun segnale, con il motivo. Meglio perdere un segnale che aprirne uno sbagliato.

Cosa conta il commento in prosa nel mezzo ("classic break and retest"...):
nulla. Si leggono solo l'intestazione e le righe che iniziano con ENTRY / SL / TP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import pairwise

from momentum_master.classifier.models import OrderHint, Side
from momentum_master.classifier.numbers import extract_numbers

# Intestazione: prima riga non vuota. Le emoji (già token EMOJI_*) sono ignorate.
_HEADER_LIMIT = re.compile(r"\bLIMIT ORDER\b\s*[-—–]+\s*(BUY|SELL)\s+XAUUSD\b", re.IGNORECASE)
_HEADER_PLAIN = re.compile(r"^(?:EMOJI_\w+\s+)*(BUY|SELL)\s+XAUUSD\b", re.IGNORECASE)
_STOP_WORDS = re.compile(r"\bSTOP\s+ORDER\b|\bBUY\s+STOP\b|\bSELL\s+STOP\b", re.IGNORECASE)

_ENTRY_SINGLE = re.compile(r"^ENTRY\s*:\s*(?P<num>\S+)\s*$", re.IGNORECASE)
_ENTRY_RANGE = re.compile(
    r"\bENTRY RANGE\s*:+\s*(?P<a>[\d.,]+)\s*[-—–]\s*(?P<b>[\d.,]+)\s*$", re.IGNORECASE
)
_SL = re.compile(r"^SL\b(?:\s*EMOJI_\w+)*\s*:\s*(?P<num>\S+)\s*$", re.IGNORECASE)
_TP = re.compile(
    r"^TP\s*(?P<idx>\d)\b[^:]*:\s*(?P<val>\S+)\s*$", re.IGNORECASE
)  # "TP1 (valuta il BE) EMOJI_WHITE_HEAVY_CHECK_MARK : 4160.66"


@dataclass(frozen=True)
class OpeningParse:
    """Esito del parsing. ``ok`` False → ``problems`` spiega perché."""

    side: Side | None = None
    order_hint: OrderHint | None = None
    entry_min: Decimal | None = None
    entry_max: Decimal | None = None
    sl: Decimal | None = None
    tps: tuple[Decimal, ...] = ()
    tp_open: bool = False
    format_id: str | None = None
    looks_like_opening: bool = False
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.looks_like_opening and not self.problems


def _single_price(raw: str) -> Decimal | None:
    tokens = extract_numbers(raw)
    if len(tokens) != 1 or tokens[0].raw != raw:
        return None
    return tokens[0].value


def parse_opening(normalized: str) -> OpeningParse:
    """Analizza un testo già normalizzato (``normalize_text``)."""
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
        return OpeningParse()

    header = lines[0]
    limit_match = _HEADER_LIMIT.search(header)
    plain_match = _HEADER_PLAIN.search(header)
    if not (limit_match or plain_match):
        return OpeningParse()  # non è un'apertura nei formati noti

    problems: list[str] = []
    side = Side((limit_match or plain_match).group(1).upper())  # type: ignore[union-attr]
    if _STOP_WORDS.search(header):
        problems.append("intestazione con STOP: formato non catalogato")
    order_hint = OrderHint.LIMIT if limit_match else OrderHint.MARKET
    format_id = "F-LIMIT" if limit_match else "F-RANGE"

    singles = [m for m in (_ENTRY_SINGLE.match(x) for x in lines[1:]) if m]
    ranges = [m for m in (_ENTRY_RANGE.search(x) for x in lines[1:]) if m]
    sls = [m for m in (_SL.match(x) for x in lines[1:]) if m]
    tp_matches = [m for m in (_TP.match(x) for x in lines[1:]) if m]

    entry_min = entry_max = None
    if format_id == "F-LIMIT":
        if len(singles) != 1 or ranges:
            problems.append(
                f"F-LIMIT: attesa 1 riga ENTRY, trovate {len(singles)} (+{len(ranges)} range)"
            )
        else:
            entry_min = entry_max = _single_price(singles[0]["num"])
            if entry_min is None:
                problems.append(f"ENTRY non leggibile: {singles[0]['num']!r}")
    else:
        if len(ranges) != 1 or singles:
            problems.append(
                f"F-RANGE: attesa 1 riga ENTRY RANGE, trovate {len(ranges)} "
                f"(+{len(singles)} singole)"
            )
        else:
            a, b = _single_price(ranges[0]["a"]), _single_price(ranges[0]["b"])
            if a is None or b is None:
                problems.append(
                    f"ENTRY RANGE non leggibile: {ranges[0]['a']!r} - {ranges[0]['b']!r}"
                )
            else:
                entry_min, entry_max = min(a, b), max(a, b)

    sl = None
    if len(sls) != 1:
        problems.append(f"attesa 1 riga SL, trovate {len(sls)}")
    else:
        sl = _single_price(sls[0]["num"])
        if sl is None:
            problems.append(f"SL non leggibile: {sls[0]['num']!r}")

    tps: list[Decimal] = []
    tp_open = False
    indexes = [int(m["idx"]) for m in tp_matches]
    if not indexes or indexes != list(range(1, len(indexes) + 1)):
        problems.append(f"TP assenti o non in sequenza 1..n: {indexes}")
    for m in tp_matches:
        value = m["val"]
        if value.upper() == "OPEN":
            if m is not tp_matches[-1]:
                problems.append("TP OPEN non in ultima posizione")
            tp_open = True
            continue
        price = _single_price(value)
        if price is None:
            problems.append(f"TP{m['idx']} non leggibile: {value!r}")
        else:
            tps.append(price)
    if tp_matches and tp_matches[0]["val"].upper() == "OPEN":
        problems.append("TP1 senza prezzo")

    # TP nella direzione del trade, strettamente crescenti (BUY) o decrescenti (SELL).
    if len(tps) >= 2:
        pairs = list(pairwise(tps))
        ordered = all(b > a for a, b in pairs) if side is Side.BUY else all(b < a for a, b in pairs)
        if not ordered:
            problems.append(f"TP non ordinati nella direzione {side}: {[str(t) for t in tps]}")

    return OpeningParse(
        side=side,
        order_hint=order_hint,
        entry_min=entry_min,
        entry_max=entry_max,
        sl=sl,
        tps=tuple(tps),
        tp_open=tp_open,
        format_id=format_id,
        looks_like_opening=True,
        problems=tuple(problems),
    )
