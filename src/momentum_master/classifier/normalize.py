"""Normalizzazione del testo prima della classificazione (punto 1.1b).

Regole:
- Unicode NFKC (cifre a larghezza piena, spazi speciali, legature → forma standard);
- rimozione di selettori di variante, zero-width e modificatori del tono della pelle;
- ogni emoji/simbolo diventa un token DESCRITTIVO, es. 🟢 → ``EMOJI_LARGE_GREEN_CIRCLE``.
  Il token descrive il simbolo, NON il suo significato: che 🟢 voglia dire BUY su
  WDT MOMENTUM va verificato sullo storico e scritto nel catalogo dei formati;
- keycap (1️⃣) → la cifra semplice;
- spazi e a capo uniformati; le righe restano separate (i TP sono spesso uno per riga).

Il testo originale non viene mai modificato: questa funzione restituisce una copia.
La formattazione Telegram (grassetto, corsivo, link) non è nel testo esportato da
Telethon (``message.message``), quindi non c'è markup da togliere.

I numeri NON vengono riscritti qui: "2,650" può essere 2650 o 2,65. L'interpretazione è
in ``classifier.numbers``, che segnala esplicitamente i casi ambigui.
"""

from __future__ import annotations

import re
import unicodedata

EMOJI_TOKEN_PREFIX = "EMOJI_"

# Caratteri da eliminare del tutto.
_DROP_CHARS = {
    "︎",  # selettore di variante testo
    "️",  # selettore di variante emoji
    "​",  # zero width space
    "‌",  # zero width non-joiner
    "‍",  # zero width joiner (unisce emoji composte: le scomponiamo)
    "⁠",  # word joiner
    "﻿",  # BOM / zero width no-break space
    "⃣",  # combining enclosing keycap: 1️⃣ → 1
}
_SKIN_TONES = range(0x1F3FB, 0x1F400)
_ARROWS_BLOCK = range(0x2190, 0x2200)  # → ← ↑ ↓ ecc. (categoria Sm, non So)
_LINE_BREAKS = {"\r\n": "\n", "\r": "\n", " ": "\n", " ": "\n", "\x85": "\n"}

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


def emoji_token(char: str) -> str:
    """Token descrittivo di un singolo simbolo, es. '🟢' → 'EMOJI_LARGE_GREEN_CIRCLE'."""
    name = unicodedata.name(char, "")
    if not name:
        return f"{EMOJI_TOKEN_PREFIX}U{ord(char):04X}"
    return EMOJI_TOKEN_PREFIX + re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def _is_symbol(char: str) -> bool:
    return unicodedata.category(char) == "So" or ord(char) in _ARROWS_BLOCK


def normalize_text(raw: str) -> str:
    """Restituisce il testo normalizzato per il classificatore."""
    text = unicodedata.normalize("NFKC", raw)
    for src, dst in _LINE_BREAKS.items():
        text = text.replace(src, dst)

    out: list[str] = []
    for char in text:
        if char in _DROP_CHARS or ord(char) in _SKIN_TONES:
            continue
        if _is_symbol(char):
            out.append(f" {emoji_token(char)} ")
        elif char == "\t" or (unicodedata.category(char) == "Zs"):
            out.append(" ")
        else:
            out.append(char)

    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in "".join(out).split("\n")]
    return _MULTI_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
