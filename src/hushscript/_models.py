from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ._errors import ApiError
from ._json import as_dict

if TYPE_CHECKING:
    from collections.abc import Mapping


def _int_field(body: Mapping[str, object], key: str) -> int:
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(f"The account response has no integer {key}.", code="unexpected_response")
    return value


@dataclass(frozen=True, slots=True)
class Balance:
    seconds: int
    """Spendable now, already net of holds; may be negative (clawback debt)."""
    minutes: int
    held_seconds: int
    expires_at: datetime | None
    purchases_remaining: int | None

    @classmethod
    def from_account(cls, body: object) -> Balance:
        fields = as_dict(body)
        if fields is None:
            raise ApiError("The account response is not a JSON object.", code="unexpected_response")
        seconds = _int_field(fields, "balance_seconds")
        expires = fields.get("credits_expire_at")
        remaining = fields.get("purchases_remaining_in_window")
        return cls(
            seconds=seconds,
            minutes=int(seconds / 60),
            held_seconds=_int_field(fields, "held_seconds"),
            expires_at=datetime.fromtimestamp(expires, tz=UTC)
            if isinstance(expires, int) and not isinstance(expires, bool)
            else None,
            purchases_remaining=remaining
            if isinstance(remaining, int) and not isinstance(remaining, bool)
            else None,
        )
