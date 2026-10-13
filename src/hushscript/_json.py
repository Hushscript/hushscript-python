from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

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


@dataclass(frozen=True, slots=True)
class ExtraFields:
    _extra: dict[str, object] = field(default_factory=dict, kw_only=True, repr=False, compare=False)

    @property
    def extra(self) -> Mapping[str, object]:
        """Unknown API fields, with a read-only mapping and independent nested values."""
        return MappingProxyType(copy.deepcopy(self._extra))


def extra_fields(body: Mapping[str, object], *known: str) -> dict[str, object]:
    return copy.deepcopy({key: value for key, value in body.items() if key not in known})
