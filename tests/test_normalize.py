import pytest

from momentum_master.classifier.normalize import emoji_token, normalize_text


def test_emoji_become_descriptive_tokens_not_meanings() -> None:
    assert normalize_text("🟢BUY GOLD") == "EMOJI_LARGE_GREEN_CIRCLE BUY GOLD"
    assert normalize_text("🔴 SELL") == "EMOJI_LARGE_RED_CIRCLE SELL"
    assert normalize_text("🥇 XAUUSD") == "EMOJI_FIRST_PLACE_MEDAL XAUUSD"


def test_variation_selector_is_removed() -> None:
    # ⬆️ = U+2B06 + U+FE0F
    assert normalize_text("⬆️ BUY") == "EMOJI_UPWARDS_BLACK_ARROW BUY"


def test_arrows_are_tokenized() -> None:
    assert normalize_text("SL→2642") == "SL EMOJI_RIGHTWARDS_ARROW 2642"


def test_keycap_digits_become_plain_digits() -> None:
    assert normalize_text("TP1️⃣ 2655") == "TP1 2655"


def test_nfkc_fullwidth_digits_and_nbsp() -> None:
    assert normalize_text("ＢＵＹ ２６５０") == "BUY 2650"


def test_zero_width_and_skin_tones_removed() -> None:
    assert normalize_text("BU​Y 👍🏽") == "BUY EMOJI_THUMBS_UP_SIGN"


def test_lines_are_kept_spaces_collapsed() -> None:
    raw = "XAUUSD   BUY\r\n\r\n\r\n\tTP1  2655 \r\nTP2 2660"
    assert normalize_text(raw) == "XAUUSD BUY\n\nTP1 2655\nTP2 2660"


def test_numbers_are_not_rewritten() -> None:
    assert normalize_text("SL 2642,5 TP 2,655") == "SL 2642,5 TP 2,655"


def test_original_string_is_untouched() -> None:
    raw = "🟢 BUY"
    normalize_text(raw)
    assert raw == "🟢 BUY"


@pytest.mark.parametrize("raw", ["", "   ", "\n\n"])
def test_empty_input(raw: str) -> None:
    assert normalize_text(raw) == ""


def test_unknown_symbol_fallback() -> None:
    assert emoji_token("\U000e0001").startswith("EMOJI_")
