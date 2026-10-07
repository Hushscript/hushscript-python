from __future__ import annotations

import json
import sys
from typing import Final, cast

_BEYOND_RANGE: Final = 2**64
_MAX_JSON_INT_DIGITS: Final = 4000


def as_dict(value: object) -> dict[str, object] | None:
    """`value` as a JSON object with typed keys, or None (isinstance alone leaves them unknown)."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def as_list(value: object) -> list[object] | None:
    """`value` as a JSON array or tuple, or None."""
    if isinstance(value, (list, tuple)):
        return list(cast("list[object]", value))
    return None


def _bounded_int(text: str) -> int:
    """An integer literal of any length: past what `int()` reads, under this interpreter's own
    limit too, it is beyond every range the SDK accepts, and keeps its sign."""
    limit = sys.get_int_max_str_digits()
    cap = min(_MAX_JSON_INT_DIGITS, limit) if limit else _MAX_JSON_INT_DIGITS
    if len(text) <= cap:
        return int(text)
    return -_BEYOND_RANGE if text.startswith("-") else _BEYOND_RANGE


def loads(data: str | bytes) -> object:
    """`json.loads` for every JSON the SDK reads: an integer literal of any length parses."""
    return json.loads(data, parse_int=_bounded_int)
