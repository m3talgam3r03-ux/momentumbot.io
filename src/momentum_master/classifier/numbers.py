"""Riconoscimento dei numeri con virgola o punto (punto 1.1b).

Principio: se un numero ha più di una lettura possibile, NON scegliamo noi.
Restituiamo tutte le letture (``candidates``) e ``is_ambiguous = True``;
decide il classificatore, col contesto (prezzo corrente, altri livelli del messaggio),
oppure il messaggio finisce in AMBIGUOUS.

Esempi:
    "2650"      → 2650
    "2650.5"    → 2650.5        "2650,5"   → 2650.5
    "2650.500"  → 2650.500      (parte intera di 4 cifre: non può essere separatore migliaia)
    "2,650"     → AMBIGUO {2650, 2.650}
    "2,650.50"  → 2650.50       "2.650,50" → 2650.50
    "06.10.2026"→ non valido (gruppi non da 3 cifre: è una data)

Il segno non viene letto: in "2650-2647" il trattino è un separatore di zona,
non un meno. I prezzi abbreviati ("47" per 2647) li risolve il classificatore.
I valori sono ``Decimal`` per evitare errori di arrotondamento dei float sui prezzi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

# Una sequenza di cifre con eventuali separatori interni ".", ",".
# Solo cifre ASCII 0-9: \d di Python accetterebbe anche cifre arabe, devanagari, ecc.
# (es. "٤١٥٨"), che nel canale non esistono e sarebbero un segnale di testo anomalo.
_NUMBER = re.compile(r"[0-9]+(?:[.,][0-9]+)*")


@dataclass(frozen=True)
class NumberToken:
    raw: str
    start: int
    end: int
    candidates: tuple[Decimal, ...]

    @property
    def is_valid(self) -> bool:
        return bool(self.candidates)

    @property
    def is_ambiguous(self) -> bool:
        return len(self.candidates) > 1

    @property
    def value(self) -> Decimal | None:
        """Il valore se unico, altrimenti None (ambiguo o non valido)."""
        return self.candidates[0] if len(self.candidates) == 1 else None


def _is_thousands_grouping(groups: list[str]) -> bool:
    """'2', '650', '000' → True: primo gruppo 1-3 cifre senza zero iniziale, poi gruppi da 3."""
    first = groups[0]
    return (
        1 <= len(first) <= 3 and not first.startswith("0") and all(len(g) == 3 for g in groups[1:])
    )


def interpret_number(raw: str) -> tuple[Decimal, ...]:
    """Tutte le letture plausibili di una stringa numerica (vuota se non valida)."""
    separators = [c for c in raw if c in ".,"]
    if not separators:
        return (Decimal(raw),)

    kinds = set(separators)
    if len(kinds) == 2:
        # Entrambi presenti: l'ultimo è il decimale, l'altro le migliaia, e deve comparire
        # solo prima del decimale ("2.650,50" sì, "2,650.5,0" no).
        decimal_sep = raw[max(raw.rfind("."), raw.rfind(","))]
        thousands_sep = "," if decimal_sep == "." else "."
        integer_part, _, fraction = raw.rpartition(decimal_sep)
        if decimal_sep in integer_part:
            return ()
        groups = integer_part.split(thousands_sep)
        if not _is_thousands_grouping(groups):
            return ()
        return (Decimal("".join(groups) + "." + fraction),)

    sep = separators[0]
    parts = raw.split(sep)
    if len(parts) > 2:
        # Stesso separatore ripetuto: solo migliaia ("2.650.000"), altrimenti non valido.
        return (Decimal("".join(parts)),) if _is_thousands_grouping(parts) else ()

    integer_part, fraction = parts
    as_decimal = Decimal(f"{integer_part}.{fraction}")
    if _is_thousands_grouping(parts):
        # "2,650" / "2.650": migliaia o decimale con 3 cifre. Non decidiamo.
        return (Decimal(integer_part + fraction), as_decimal)
    return (as_decimal,)


def extract_numbers(text: str) -> list[NumberToken]:
    """Trova tutti i numeri nel testo con posizione e letture possibili."""
    tokens: list[NumberToken] = []
    for match in _NUMBER.finditer(text):
        raw = match.group()
        tokens.append(NumberToken(raw, match.start(), match.end(), interpret_number(raw)))
    return tokens
