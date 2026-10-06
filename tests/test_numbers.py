from decimal import Decimal

import pytest

from momentum_master.classifier.numbers import extract_numbers, interpret_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2650", (Decimal("2650"),)),
        ("2650.5", (Decimal("2650.5"),)),
        ("2650,5", (Decimal("2650.5"),)),
        ("2650.50", (Decimal("2650.50"),)),
        ("2650,50", (Decimal("2650.50"),)),
        ("2650.500", (Decimal("2650.500"),)),  # parte intera di 4 cifre: decimale certo
        ("2,650.50", (Decimal("2650.50"),)),
        ("2.650,50", (Decimal("2650.50"),)),
        ("2.650.000", (Decimal("2650000"),)),
        ("0,650", (Decimal("0.650"),)),  # zero iniziale: non può essere migliaia
        ("4,8", (Decimal("4.8"),)),
    ],
)
def test_unambiguous_numbers(raw: str, expected: tuple[Decimal, ...]) -> None:
    assert interpret_number(raw) == expected


@pytest.mark.parametrize("raw", ["2,650", "2.650", "4.800"])
def test_thousands_or_decimal_is_ambiguous(raw: str) -> None:
    candidates = interpret_number(raw)
    assert len(candidates) == 2  # non scegliamo noi


@pytest.mark.parametrize("raw", ["06.10.2026", "2650.5.3", "2,650.5,0", "26,50.5"])
def test_invalid_numbers_have_no_reading(raw: str) -> None:
    assert interpret_number(raw) == ()


def test_extract_zone_keeps_both_ends_without_sign() -> None:
    tokens = extract_numbers("BUY 2650-2647 SL 2642")
    assert [t.value for t in tokens] == [Decimal("2650"), Decimal("2647"), Decimal("2642")]


def test_extract_reports_positions_and_ambiguity() -> None:
    text = "SELL 2,650 TP 2645.5"
    first, second = extract_numbers(text)
    assert text[first.start : first.end] == "2,650"
    assert first.is_ambiguous and first.value is None
    assert second.value == Decimal("2645.5")


def test_extract_numbers_attached_to_labels() -> None:
    # "TP1" contiene un numero: il classificatore lo riconoscerà come etichetta dal contesto.
    tokens = extract_numbers("TP1 2655")
    assert [t.raw for t in tokens] == ["1", "2655"]
