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

Controlli di PLAUSIBILITÀ della lettura (un numero letto male non deve mai arrivare
al motore decisionale). Valori ricavati dal catalogo, con ampio margine:
- range largo più di 0 e al massimo MAX_RANGE_WIDTH (osservato: sempre 1,00);
- SL e tutti i TP entro MAX_LEVEL_DISTANCE dal centro dell'entrata (osservato: SL ≤ 8,50,
  TP4 ≤ 16,50). Blocca le cifre perse o in più: "415.15" invece di "4155.15";
- al massimo MAX_DECIMALS decimali (il canale ne usa sempre 2);
- SL e TP dalla parte giusta per la direzione;
- intestazione con una sola direzione;
- ogni riga che inizia con ENTRY/SL/TP e contiene ":" deve essere letta per intero,
  altrimenti è un problema (nessuna riga di livelli ignorata in silenzio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import pairwise

from momentum_master.classifier.models import OrderHint, Side
from momentum_master.classifier.numbers import extract_numbers

MAX_RANGE_WIDTH = Decimal("3.00")
MAX_LEVEL_DISTANCE = Decimal("30.00")
MAX_DECIMALS = 2

# Intestazione: prima riga non vuota. Le emoji (già token EMOJI_*) sono ignorate.
_HEADER_LIMIT = re.compile(r"\bLIMIT ORDER\b\s*[-—–]+\s*(BUY|SELL)\s+XAUUSD\b", re.IGNORECASE)
_HEADER_PLAIN = re.compile(r"^(?:EMOJI_\w+\s+)*(BUY|SELL)\s+XAUUSD\b", re.IGNORECASE)
_STOP_WORDS = re.compile(r"\bSTOP\s+ORDER\b|\bBUY\s+STOP\b|\bSELL\s+STOP\b", re.IGNORECASE)

_ENTRY_SINGLE = re.compile(r"^ENTRY\s*:\s*(?P<num>\S+)\s*$", re.IGNORECASE)
_ENTRY_RANGE = re.compile(
    r"\bENTRY RANGE\s*:+\s*(?P<a>[\d.,]+)\s*[-—–]\s*(?P<b>[\d.,]+)\s*$", re.IGNORECASE
)
_SL = re.compile(r"^SL\b(?:\s*EMOJI_\w+)*\s*:\s*(?P<num>\S+)\s*$", re.IGNORECASE)
_SIDE_WORD = re.compile(r"\b(BUY|SELL)\b", re.IGNORECASE)
_SYMBOL_WORD = re.compile(r"\bXAUUSD\b", re.IGNORECASE)
# Riga che "sembra" un livello: deve corrispondere a uno dei formati sopra, altrimenti errore.
_LEVEL_LIKE = re.compile(r"^(?:ENTRY|SL|TP\s*\d)\b.*:\s*\S", re.IGNORECASE)
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
    """Il valore se ``raw`` è esattamente UN prezzo leggibile senza ambiguità, altrimenti None."""
    tokens = extract_numbers(raw)
    if len(tokens) != 1 or tokens[0].raw != raw or raw.startswith("0"):
        return None  # più numeri, caratteri estranei o zero iniziale ("04146.99")
    value = tokens[0].value
    if value is None or value <= 0 or -value.as_tuple().exponent > MAX_DECIMALS:  # type: ignore[operator]
        return None
    return value


def _plausibility_problems(
    side: Side,
    entry_min: Decimal,
    entry_max: Decimal,
    sl: Decimal,
    tps: list[Decimal],
    is_range: bool,
) -> list[str]:
    problems: list[str] = []
    width = entry_max - entry_min
    if is_range and not (Decimal("0") < width <= MAX_RANGE_WIDTH):
        problems.append(f"range largo {width}: atteso tra 0 e {MAX_RANGE_WIDTH} (refuso?)")
    center = (entry_min + entry_max) / 2
    for name, level in [("SL", sl), *((f"TP{i}", t) for i, t in enumerate(tps, start=1))]:
        if abs(level - center) > MAX_LEVEL_DISTANCE:
            problems.append(
                f"{name} {level} a {abs(level - center)} dall'entrata: oltre "
                f"{MAX_LEVEL_DISTANCE}, probabile cifra persa o in più"
            )
    if side is Side.BUY:
        wrong = sl >= entry_min or any(t <= entry_max for t in tps)
    else:
        wrong = sl <= entry_max or any(t >= entry_min for t in tps)
    if wrong:
        problems.append(f"livelli dalla parte sbagliata per un {side}")
    return problems


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
    if len(_SIDE_WORD.findall(header)) != 1 or len(_SYMBOL_WORD.findall(header)) != 1:
        problems.append("intestazione con più direzioni o più simboli")
    if _STOP_WORDS.search(header):
        problems.append("intestazione con STOP: formato non catalogato")
    order_hint = OrderHint.LIMIT if limit_match else OrderHint.MARKET
    format_id = "F-LIMIT" if limit_match else "F-RANGE"

    singles = [m for m in (_ENTRY_SINGLE.match(x) for x in lines[1:]) if m]
    ranges = [m for m in (_ENTRY_RANGE.search(x) for x in lines[1:]) if m]
    sls = [m for m in (_SL.match(x) for x in lines[1:]) if m]
    tp_matches = [m for m in (_TP.match(x) for x in lines[1:]) if m]
    for line in lines[1:]:
        if _LEVEL_LIKE.match(line) and not (
            _ENTRY_SINGLE.match(line)
            or _ENTRY_RANGE.search(line)
            or _SL.match(line)
            or _TP.match(line)
        ):
            problems.append(f"riga di livello non leggibile per intero: {line!r}")

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

    if entry_min is not None and entry_max is not None and sl is not None and tps:
        problems += _plausibility_problems(
            side, entry_min, entry_max, sl, tps, is_range=format_id == "F-RANGE"
        )

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
