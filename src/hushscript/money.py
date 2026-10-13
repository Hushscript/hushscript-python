from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ._json import ExtraFields


@dataclass(frozen=True, slots=True)
class Money(ExtraFields):
    """A price as the API states it, with a display string in the `en` locale.

    The amount digits and the grouping (minor-unit digits from Stripe's table, thousands grouped
    with commas) are the same in every Hushscript SDK. The rest of `formatted` is this SDK's own: it
    writes `$`, `€`, `£` or `¥` for USD, EUR, GBP and JPY, and for every other known currency the
    code and a no-break space before the number (`KRW 1,234`), where the TypeScript SDK takes its
    symbols from Intl and may print another. Compare `amount` and `currency`, never `formatted`,
    across SDKs.
    """

    amount: int
    """In the currency's minor units, from the API."""
    currency: str
    """The ISO 4217 code as the API sends it."""
    formatted: str
    """`amount` divided by Stripe's minor-unit digits for the currency, for example `$5.99`."""


# Stripe's minor-unit digits, which the API's amounts use (spec 6.5). They come from this table and
# never from locale data: ICU disagrees for IDR, HUF, ISK and others.
_ZERO_DIGITS: Final = frozenset(
    "BIF CLP DJF GNF JPY KMF KRW MGA PYG RWF UGX VND VUV XAF XOF XPF".split()  # noqa: SIM905
)
_THREE_DIGITS: Final = frozenset("BHD JOD KWD OMR TND".split())  # noqa: SIM905
# The ISO 4217 codes printed with the code in front; any other string is shown plainly, as
# "5.99 ZZZ", and never fails.
_KNOWN: Final = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD
    BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB
    EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK
    JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA
    MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK
    PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN
    SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VES VND VUV WST
    XAF XCD XOF XPF YER ZAR ZMW ZWG
    """.split()  # noqa: SIM905
)
_SYMBOLS: Final = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
_NO_BREAK_SPACE: Final = chr(0xA0)
_ZERO_DIGIT_COUNT: Final = 0
_THREE_DIGIT_COUNT: Final = 3
_DEFAULT_DIGITS: Final = 2


def minor_unit_digits(code: str) -> int:
    if code in _ZERO_DIGITS:
        return _ZERO_DIGIT_COUNT
    return _THREE_DIGIT_COUNT if code in _THREE_DIGITS else _DEFAULT_DIGITS


def to_money(amount: int, currency: str) -> Money:
    """The `Money` of an API amount and currency; an unknown currency is shown as the plain amount
    and the upper-cased code with 2 digits, and never raises."""
    code = currency.upper()
    digits = minor_unit_digits(code)
    magnitude = abs(amount)
    whole, fraction = divmod(magnitude, 10**digits)
    known = code in _KNOWN
    number = f"{whole:,}" if known else str(whole)
    if digits:
        number += f".{fraction:0{digits}d}"
    sign = "-" if amount < 0 else ""
    if not known:
        return Money(amount, currency, f"{sign}{number} {code}")
    symbol = _SYMBOLS.get(code)
    if symbol is not None:
        return Money(amount, currency, f"{sign}{symbol}{number}")
    return Money(amount, currency, f"{sign}{code}{_NO_BREAK_SPACE}{number}")
