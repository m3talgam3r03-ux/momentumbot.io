"""Sicurezza della LETTURA: il classificatore non deve mai leggere un numero diverso da
quello scritto, né accettare livelli implausibili (cifre perse o in più).

Tre livelli di prova:
1. casi d'attacco trovati nella revisione del 2026-10-06 (regressione);
2. mutazioni mirate su ogni prezzo di ogni messaggio reale;
3. fuzzing: messaggi reali rovinati a caso; se il messaggio viene accettato, ogni numero
   letto deve comparire LETTERALMENTE nel testo e rispettare i limiti di plausibilità.
"""

from __future__ import annotations

import random
import re
from decimal import Decimal

import pytest

from golden_messages import GOLDEN_OPENINGS
from momentum_master.classifier.normalize import normalize_text
from momentum_master.classifier.numbers import extract_numbers
from momentum_master.classifier.opening import (
    MAX_LEVEL_DISTANCE,
    MAX_RANGE_WIDTH,
    OpeningParse,
    parse_opening,
)

TEXT = {c["id"]: c["text"] for c in GOLDEN_OPENINGS}


def parse(text: str) -> OpeningParse:
    return parse_opening(normalize_text(text))


# --- 1. casi d'attacco (regressione) ----------------------------------------------------

ATTACKS = {
    "range abbreviato": ("range_sell_1", "4138.96 - 4139.96", "4138.96 - 39.96"),
    "range con refuso largo": ("range_sell_1", "4138.96 - 4139.96", "4138.96 - 4193.96"),
    "range a larghezza zero": ("range_sell_1", "4138.96 - 4139.96", "4138.96 - 4138.96"),
    "SL BUY senza una cifra": ("range_buy_1", "SL ❌: 4155.15", "SL ❌: 415.15"),
    "SL con una cifra in più": ("limit_buy_1", "SL ❌: 4153.16", "SL ❌: 41153.16"),
    "TP4 senza una cifra": ("range_sell_1", "4122.46", "412.46"),
    "TP1 senza una cifra": ("range_sell_1", "4134.36", "413.36"),
    "entrata senza una cifra": ("limit_buy_1", "ENTRY: 4158.16", "ENTRY: 415.16"),
    "cifre arabe": ("limit_buy_1", "ENTRY: 4158.16", "ENTRY: ٤١٥٨.16"),
    "BUY e SELL in intestazione": ("range_sell_1", "SELL XAUUSD (GOLD)", "SELL XAUUSD (GOLD) BUY"),
    "doppio simbolo": ("range_sell_1", "SELL XAUUSD (GOLD)", "SELL XAUUSD XAUUSD"),
    "prezzo a 3 decimali": ("limit_buy_1", "4153.16", "4153.165"),
    "prezzo negativo": ("limit_buy_1", "SL ❌: 4153.16", "SL ❌: -4153.16"),
    "prezzo zero": ("limit_buy_1", "SL ❌: 4153.16", "SL ❌: 0"),
    "SL dalla parte sbagliata": ("limit_buy_1", "SL ❌: 4153.16", "SL ❌: 4163.16"),
    "TP1 dalla parte sbagliata": ("limit_buy_1", "4160.66", "4155.66"),
    "riga TP senza due punti": ("range_sell_1", "TP3✅: 4126.71", "TP3✅ 4126.71"),
    "riga SL con nota": ("limit_buy_1", "SL ❌: 4153.16", "SL ❌: 4153.16 (stretto)"),
    "lettera O al posto di zero": ("range_sell_2", "4115.80", "4115.8O"),
    "zero iniziale": ("range_sell_4", "TP2 (metti a BE)✅: 4146.99", "TP2 (metti a BE)✅: 04146.99"),  # noqa: E501
}  # fmt: skip


@pytest.mark.parametrize("name", list(ATTACKS))
def test_attack_is_rejected(name: str) -> None:
    signal, old, new = ATTACKS[name]
    assert old in TEXT[signal], "il caso d'attacco non si applica più al messaggio"
    result = parse(TEXT[signal].replace(old, new, 1))
    assert not result.ok, f"{name}: accettato → {result}"


def test_range_split_on_real_newline_is_still_read() -> None:
    # Se "%0A" nel testo vero fosse un a capo, la riga ENTRY RANGE va letta lo stesso.
    text = TEXT["range_sell_1"].replace("   %0A ➡️ ENTRY RANGE", "\nENTRY RANGE")
    result = parse(text)
    assert result.ok, result.problems
    assert (result.entry_min, result.entry_max) == (Decimal("4138.96"), Decimal("4139.96"))


def test_golden_messages_respect_plausibility_limits() -> None:
    for case in GOLDEN_OPENINGS:
        result = parse(case["text"])
        assert result.ok, (case["id"], result.problems)


# --- 2. mutazioni mirate su ogni prezzo ----------------------------------------------------

_LEVEL_LINE = re.compile(r"^(?:.*ENTRY RANGE.*|ENTRY:.*|SL .*|TP\d.*)$", re.MULTILINE)
_PRICE = re.compile(r"\d{4}\.\d{2}")


def _mutations(price: str) -> list[str]:
    integer, decimals = price.split(".")
    return [
        integer[1:] + "." + decimals,  # cifra iniziale persa
        integer[:-1] + "." + decimals,  # cifra finale dell'intero persa
        integer + integer[-1] + "." + decimals,  # cifra in più
        "1" + price,  # cifra in testa
        integer + decimals,  # punto perso: 415816
        integer + ".." + decimals,  # punto doppio
        integer + "." + decimals + "5",  # terzo decimale
        integer.replace(integer[1], "O", 1) + "." + decimals,  # lettera nell'intero
        "-" + price,  # segno
        integer + "," + decimals[0] + "," + decimals[1],  # separatori impazziti
    ]


def _targeted_cases() -> list[tuple[str, str, str]]:
    cases = []
    for case in GOLDEN_OPENINGS:
        text = case["text"]
        for line in _LEVEL_LINE.findall(text):
            for price in _PRICE.findall(line):
                for mutated in _mutations(price):
                    new_line = line.replace(price, mutated, 1)
                    cases.append(
                        (case["id"], text.replace(line, new_line, 1), f"{price}→{mutated}")
                    )
    return cases


TARGETED = _targeted_cases()


def test_targeted_mutations_exist() -> None:
    assert len(TARGETED) > 400  # 12 messaggi × ~7 prezzi × 10 mutazioni


@pytest.mark.parametrize(("signal", "text", "label"), TARGETED, ids=[t[2] for t in TARGETED])
def test_mutated_price_is_never_accepted(signal: str, text: str, label: str) -> None:
    assert not parse(text).ok, f"{signal}: mutazione {label} accettata"


# --- 3. fuzzing: lettura letterale ---------------------------------------------------------

_ALPHABET = "0123456789.,:- ABCDEFGHIJKLMNOPQRSTUVWXYZabc\n❌✅"


def _random_mutation(text: str, rng: random.Random) -> str:
    i = rng.randrange(len(text))
    kind = rng.randrange(4)
    if kind == 0:  # cancella
        return text[:i] + text[i + 1 :]
    if kind == 1:  # inserisce
        return text[:i] + rng.choice(_ALPHABET) + text[i:]
    if kind == 2:  # sostituisce
        return text[:i] + rng.choice(_ALPHABET) + text[i + 1 :]
    j = min(i + 1, len(text) - 1)  # scambia due caratteri vicini
    return text[:i] + text[j] + text[i] + text[j + 1 :]


def _check_literal_reading(original_id: str, mutated: str) -> None:
    result = parse(mutated)
    if not result.ok:
        return
    normalized = normalize_text(mutated)
    header = normalized.split("\n", 1)[0].upper()
    assert result.side is not None and result.side.value in header
    levels = [result.entry_min, result.entry_max, result.sl, *result.tps]
    # Ogni valore letto deve essere uno dei numeri SCRITTI nel testo (letti senza ambiguità).
    written = {t.value for t in extract_numbers(normalized) if t.value is not None}
    for value in levels:
        assert value is not None and value > 0
        assert value in written, f"{original_id}: letto {value} che non è scritto nel testo"
    center = (result.entry_min + result.entry_max) / 2  # type: ignore[operator]
    assert result.entry_max - result.entry_min <= MAX_RANGE_WIDTH  # type: ignore[operator]
    assert all(abs(v - center) <= MAX_LEVEL_DISTANCE for v in [result.sl, *result.tps])  # type: ignore[operator]


@pytest.mark.parametrize("case", GOLDEN_OPENINGS, ids=[c["id"] for c in GOLDEN_OPENINGS])
def test_fuzz_single_mutations(case: dict) -> None:
    rng = random.Random(f"momentum-{case['id']}")
    for _ in range(400):
        _check_literal_reading(case["id"], _random_mutation(case["text"], rng))


@pytest.mark.parametrize("case", GOLDEN_OPENINGS, ids=[c["id"] for c in GOLDEN_OPENINGS])
def test_fuzz_multiple_mutations(case: dict) -> None:
    rng = random.Random(f"momentum-multi-{case['id']}")
    for _ in range(200):
        text = case["text"]
        for _ in range(rng.randint(2, 6)):
            text = _random_mutation(text, rng)
        _check_literal_reading(case["id"], text)
