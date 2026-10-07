from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from hushscript import Money
from hushscript.money import to_money

NBSP = chr(0xA0)


def test_money_is_formatted_from_stripes_minor_unit_digits_never_from_locale_data() -> None:
    table = [
        (599, "USD", "$5.99"),
        (1, "USD", "$0.01"),
        (0, "USD", "$0.00"),
        (150_000, "USD", "$1,500.00"),
        (500, "JPY", "¥500"),
        (1500, "KWD", f"KWD{NBSP}1.500"),
        (3499, "EUR", "€34.99"),
        (1250, "GBP", "£12.50"),
        # Stripe counts two minor digits where ICU counts none: the price is 100 times smaller.
        (1_500_000, "IDR", f"IDR{NBSP}15,000.00"),
        (150_000, "HUF", f"HUF{NBSP}1,500.00"),
        (150_000, "ISK", f"ISK{NBSP}1,500.00"),
        (150_000, "COP", f"COP{NBSP}1,500.00"),
        # ... and two where ICU counts three.
        (1500, "LYD", f"LYD{NBSP}15.00"),
        (1500, "BHD", f"BHD{NBSP}1.500"),
        (250, "usd", "$2.50"),
        (-599, "USD", "-$5.99"),
        (-1500, "KWD", f"-KWD{NBSP}1.500"),
        (1_234_567_890, "USD", "$12,345,678.90"),
    ]
    for amount, currency, formatted in table:
        assert to_money(amount, currency) == Money(amount, currency, formatted)


def test_every_zero_and_three_digit_currency_of_the_table_has_its_digits() -> None:
    zero = [
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    ]
    for code in zero:
        expected = "¥1,234" if code == "JPY" else f"{code}{NBSP}1,234"
        assert to_money(1234, code).formatted == expected
    for code in ["BHD", "JOD", "KWD", "OMR", "TND"]:
        assert to_money(1234, code).formatted == f"{code}{NBSP}1.234"


def test_an_unknown_currency_is_a_plain_amount_and_code_with_two_digits_and_never_fails() -> None:
    for currency in ("ZZZ", "ZZZZ", "", "us", "x1"):
        assert to_money(599, currency) == Money(599, currency, f"5.99 {currency.upper()}")
    assert to_money(-150_000, "zzz").formatted == "-1500.00 ZZZ"


@given(st.integers(min_value=-(2**80), max_value=2**80), st.text(max_size=12))
def test_money_never_raises_for_any_amount_and_currency(amount: int, currency: str) -> None:
    money = to_money(amount, currency)
    assert (money.amount, money.currency) == (amount, currency)
    assert money.formatted
