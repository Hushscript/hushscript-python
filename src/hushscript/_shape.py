from __future__ import annotations

import math
from collections.abc import Callable, Mapping  # the Shape alias is built at runtime
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, TypeAlias

from ._json import as_dict, as_list
from ._response import BadBodyError

INT_LIMIT: Final = 2**63
"""Whole numbers in a body stay inside a signed 64-bit range, as the API's own counters do."""
MAX_UNIX_SECONDS: Final = 253_402_300_799
"""9999-12-31T23:59:59Z: the last instant a `datetime` holds."""
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Problem:
    """Where a body departs from its shape: the path to the field and what was expected there."""

    path: tuple[str | int, ...]
    expected: str

    def under(self, step: str | int) -> Problem:
        return Problem((step, *self.path), self.expected)

    def describe(self) -> str:
        where = ""
        for part in self.path:
            if isinstance(part, int):
                where += f"[{part}]"
            else:
                where += f".{part}" if where else part
        return f"{where}: expected {self.expected}" if where else f"expected {self.expected}"


Shape: TypeAlias = Callable[[object], Problem | None]


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def string(value: object) -> Problem | None:
    return None if isinstance(value, str) else Problem((), "a string")


def boolean(value: object) -> Problem | None:
    return None if isinstance(value, bool) else Problem((), "a boolean")


def integer(value: object) -> Problem | None:
    whole = _whole(value)
    return None if whole is not None and abs(whole) < INT_LIMIT else Problem((), "a whole number")


def count(value: object) -> Problem | None:
    """A quantity that cannot be negative: seconds, bytes, jobs."""
    whole = _whole(value)
    ok = whole is not None and 0 <= whole < INT_LIMIT
    return None if ok else Problem((), "a whole number of 0 or more")


def positive(value: object) -> Problem | None:
    whole = _whole(value)
    return None if whole is not None and 0 < whole < INT_LIMIT else Problem((), "a number above 0")


def number(value: object) -> Problem | None:
    """A finite number; `NaN` and `Infinity` parse in Python but are not JSON."""
    ok = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) < INT_LIMIT
    )
    return None if ok else Problem((), "a number")


def timestamp(value: object) -> Problem | None:
    whole = _whole(value)
    ok = whole is not None and 0 <= whole <= MAX_UNIX_SECONDS
    return None if ok else Problem((), "a unix timestamp in seconds")


def anything(_value: object) -> Problem | None:
    return None


def nullable(shape: Shape) -> Shape:
    return lambda value: None if value is None else shape(value)


def array_of(shape: Shape) -> Shape:
    def check(value: object) -> Problem | None:
        items = as_list(value)
        if items is None:
            return Problem((), "an array")
        for index, item in enumerate(items):
            found = shape(item)
            if found is not None:
                return found.under(index)
        return None

    return check


def record_of(shape: Shape) -> Shape:
    """An object with arbitrary keys whose values all fit `shape`."""

    def check(value: object) -> Problem | None:
        fields = as_dict(value)
        if fields is None:
            return Problem((), "an object")
        for key, item in fields.items():
            found = shape(item)
            if found is not None:
                return found.under(key)
        return None

    return check


def object_of(required: Mapping[str, Shape], optional: Mapping[str, Shape] | None = None) -> Shape:
    """An object with each required key present and fitting, and each optional key fitting when it
    is there. Keys the shape does not list pass, so a newer API still parses."""
    extras = optional or {}

    def check(value: object) -> Problem | None:
        fields = as_dict(value)
        if fields is None:
            return Problem((), "an object")
        for key, shape in required.items():
            found = shape(fields[key]) if key in fields else Problem((), "a value")
            if found is not None:
                return found.under(key)
        for key, shape in extras.items():
            found = shape(fields[key]) if key in fields else None
            if found is not None:
                return found.under(key)
        return None

    return check


def check_shape(value: object, shape: Shape, what: str) -> None:
    """Raises BadBodyError naming the path and the expectation, never the value, when `value` does
    not fit `shape`."""
    found = shape(value)
    if found is not None:
        raise BadBodyError(f"{what} ({found.describe()})")


def to_datetime(seconds: object) -> datetime:
    """The aware UTC `datetime` of a unix timestamp that the `timestamp` shape accepted."""
    whole = _whole(seconds)
    if whole is None:
        raise BadBodyError("a timestamp (not a whole number)")
    return _EPOCH + timedelta(seconds=whole)


def as_whole(value: object) -> int:
    """`value` as an int once the shape has vouched for it; a stray type is BadBodyError, never
    a TypeError at a later line."""
    whole = _whole(value)
    if whole is None:
        raise BadBodyError("a whole number")
    return whole


def as_text(value: object) -> str:
    if not isinstance(value, str):
        raise BadBodyError("a string")
    return value


def as_flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise BadBodyError("a boolean")
    return value


def maybe_whole(value: object) -> int | None:
    return None if value is None else as_whole(value)


def maybe_text(value: object) -> str | None:
    return None if value is None else as_text(value)


def maybe_flag(value: object) -> bool | None:
    return None if value is None else as_flag(value)
