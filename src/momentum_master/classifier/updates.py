"""Riconoscimento dei messaggi che NON sono aperture: aggiornamenti, risultati, rumore.

Formati ricavati dallo storico reale (1976 messaggi, 26/08 → 06/10/2026; vedi
docs/catalogo_formati.md). Si guarda la PRIMA riga del testo normalizzato.

| Prima riga                                   | Categoria            |
|----------------------------------------------|----------------------|
| "❌ LIMIT ORDER CANCELLED"                    | CANCEL               |
| "OUT OF TRADE ✅" / "TRADE COMPLETE ✅"        | CLOSE_FULL           |
| "TPn … HIT" + "Porta lo STOP LOSS al prezzo" | MOVE_BE (con tp_hit) |
| "TPn … HIT"                                  | RESULT_ANNOUNCEMENT  |
| "SL … HIT"                                   | RESULT_ANNOUNCEMENT  |
| "🎯 LIMIT ORDER FILLED"                       | RESULT_ANNOUNCEMENT  |
| "⚠️ HEADS UP — …"                             | AMBIGUOUS (D4: solo notifica all'admin) |
| pre-annunci "PREPARA…", "PREPARATI…", "PREP |"| NOISE                |
| riepiloghi giornalieri/settimanali           | NOISE                |
| testo senza livelli né parole operative      | NOISE                |
| tutto il resto                               | AMBIGUOUS            |

Principio: in caso di dubbio AMBIGUOUS (notifica), mai NOISE. Un testo diventa NOISE
"generico" solo se non contiene NESSUNA parola operativa e NESSUN numero da prezzo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from momentum_master.classifier.models import Category
from momentum_master.classifier.numbers import extract_numbers


@dataclass(frozen=True)
class UpdateMatch:
    category: Category
    kind: str  # etichetta leggibile: LIMIT_CANCELLED, OUT_OF_TRADE, TP_HIT, ...
    tp_hit: int | None = None


_FIRST_RULES: tuple[tuple[re.Pattern[str], Category, str], ...] = (
    (re.compile(r"\bLIMIT ORDER CANCELL?ED\b"), Category.CANCEL, "LIMIT_CANCELLED"),
    (re.compile(r"^(?:EMOJI_\w+\s*)*OUT OF TRADE\b"), Category.CLOSE_FULL, "OUT_OF_TRADE"),
    (re.compile(r"^(?:EMOJI_\w+\s*)*TRADE COMPLETE\b"), Category.CLOSE_FULL, "TRADE_COMPLETE"),
    (re.compile(r"\bLIMIT ORDER FILLED\b"), Category.RESULT_ANNOUNCEMENT, "LIMIT_FILLED"),
    (re.compile(r"^(?:EMOJI_\w+\s*)*SL\b.*\bHIT\b"), Category.RESULT_ANNOUNCEMENT, "SL_HIT"),
    (re.compile(r"^(?:EMOJI_\w+\s*)*HEADS UP\b"), Category.AMBIGUOUS, "HEADS_UP"),
    (re.compile(r"^(?:EMOJI_\w+\s*)*PREP(?:ARA|ARATI)?\b"), Category.NOISE, "PRE_ANNUNCIO"),
)
_TP_HIT = re.compile(r"^(?:EMOJI_\w+\s*)*TP\s*(\d)\b.*\bHIT\b")
# Istruzione esplicita di pareggio, cercata nelle righe DOPO la prima: l'etichetta
# "TP1 (valuta il BE)" nella prima riga è solo il nome del TP, non un'istruzione.
_BE_INSTRUCTION = re.compile(
    r"PORTA LO STOP LOSS AL PREZZO D|MOVE SL TO ENTRY|SPOSTA LO SL|STOP LOSS AL PREZZO D|"
    r"BREAK ?EVEN"
)
_SUMMARY = re.compile(
    r"RISULTATI GIORNALIERI|RISULTATI SETTIMANALI|PERFORMANCE REVIEW|WEEKLY SUMMARY|"
    r"DAILY SUMMARY|"
    r"REGOLE DI TRADING"
)
# Parole che possono indicare un'istruzione operativa: se presenti, mai NOISE generico.
_OPERATIVE = re.compile(
    r"\b(?:SL|TP\d?|ENTRY|ENTRATA|BUY|SELL|LONG|SHORT|CLOSE|CLOSED|CLOSING|CHIUD\w*|"
    r"CANCEL\w*|ANNULL\w*|EXIT\w*|OUT|BE|BREAK ?EVEN|PAREGGIO|LIMIT|STOP|PENDING|"
    r"PENDENTE|MOVE|SPOST\w*|HIT|NOW|ORA|ADESSO|RIENTR\w*|RE-?ENTER\w*|AGAIN|ADD|"
    r"ENTRA\w*|APRI\w*|COMPRA\w*|VENDI\w*)\b"
)
_PRICE_LIKE_MIN = 1000
# Istruzioni "forti": se compaiono, una didascalia non è mai rumore.
_STRONG_INSTRUCTION = re.compile(
    r"\b(?:SL|TP\d?|ENTRY|CLOSE|CLOSED|CLOSING|CHIUD\w*|CANCEL\w*|ANNULL\w*|EXIT\w*|"
    r"OUT OF TRADE|BE|BREAK ?EVEN|PAREGGIO|MOVE|SPOST\w*|LIMIT|PENDING|PENDENTE|"
    r"BUY|SELL|RIENTR\w*|RE-?ENTER\w*|AGAIN)\b"
)


def is_chart_caption(normalized: str, has_media: bool, is_reply: bool) -> bool:
    """Foto/GIF in risposta a un messaggio, con una didascalia senza istruzioni forti.

    Nello storico sono ~180 commenti ai grafici ("Patience rewarded — XAUUSD finally came
    to our level…", "First stop 4550.35"). Un prezzo nel testo non basta a farne
    un'istruzione: lo fanno solo le parole di _STRONG_INSTRUCTION.
    """
    return has_media and is_reply and not _STRONG_INSTRUCTION.search(normalized.upper())


def classify_update(normalized: str) -> UpdateMatch | None:
    """Categoria di un messaggio non di apertura, o None se nessuna regola si applica."""
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
        return None
    first = lines[0].upper()
    whole = normalized.upper()

    tp = _TP_HIT.match(first)
    if tp:
        index = int(tp.group(1))
        if _BE_INSTRUCTION.search("\n".join(lines[1:]).upper()):
            return UpdateMatch(Category.MOVE_BE, "TP_HIT_BE", index)
        return UpdateMatch(Category.RESULT_ANNOUNCEMENT, "TP_HIT", index)
    for pattern, category, kind in _FIRST_RULES:
        if pattern.search(first):
            return UpdateMatch(category, kind)
    if _SUMMARY.search(whole):
        return UpdateMatch(Category.NOISE, "RIEPILOGO")
    return None


def is_generic_noise(normalized: str) -> bool:
    """Vero solo se il testo non ha parole operative né numeri che sembrano prezzi."""
    text = normalized.upper()
    if _OPERATIVE.search(text):
        return False
    return not any(
        t.value is not None and t.value >= _PRICE_LIKE_MIN for t in extract_numbers(text)
    )
