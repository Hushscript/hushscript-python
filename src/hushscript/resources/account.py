from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hushscript._json import ExtraFields, as_dict, extra_fields
from hushscript._shape import as_flag, as_text, as_whole, check_shape, maybe_whole, to_datetime
from hushscript._shapes import ACCOUNT, BALANCE

if TYPE_CHECKING:
    from datetime import datetime


def _expiry(fields: dict[str, object]) -> datetime | None:
    expires = fields.get("credits_expire_at")
    return None if expires is None else to_datetime(expires)


def minutes_of(seconds: int) -> int:
    """`seconds / 60` rounded toward zero, exact for any size of int."""
    return seconds // 60 if seconds >= 0 else -(-seconds // 60)


@dataclass(frozen=True, slots=True)
class Balance(ExtraFields):
    seconds: int
    """Spendable now, already net of holds (not "balance minus held"); may be negative
    (clawback debt)."""
    minutes: int
    """`seconds / 60`, rounded toward zero."""
    held_seconds: int
    """Committed to in-flight jobs, and already deducted from `seconds`."""
    expires_at: datetime | None
    purchases_remaining: int | None
    """Agent accounts only, else None."""

    @classmethod
    def from_account(cls, body: object) -> Balance:
        check_shape(body, BALANCE, "account response")
        fields = as_dict(body) or {}
        seconds = as_whole(fields["balance_seconds"])
        return cls(
            _extra=extra_fields(
                fields,
                "balance_seconds",
                "held_seconds",
                "credits_expire_at",
                "purchases_remaining_in_window",
            ),
            seconds=seconds,
            minutes=minutes_of(seconds),
            held_seconds=as_whole(fields["held_seconds"]),
            expires_at=_expiry(fields),
            purchases_remaining=maybe_whole(fields.get("purchases_remaining_in_window")),
        )


@dataclass(frozen=True, slots=True)
class UploadLimits(ExtraFields):
    """The caller's upload admission limits. Unknown API keys remain available in `extra`."""

    max_daily_seconds: int
    """The daily transcription cap, in seconds."""
    max_active_jobs: int
    """The most pipeline jobs in flight at once."""
    active_jobs: int
    """Pipeline jobs in flight now."""
    used_today_seconds: int
    """Billable seconds used today."""


@dataclass(frozen=True, slots=True)
class Account(ExtraFields):
    balance_seconds: int
    """Net of holds and clawback debt; may be negative."""
    held_seconds: int
    """Committed to in-flight jobs, and already deducted from `balance_seconds`."""
    credits_expire_at: datetime | None
    card_on_file: bool
    data_region: str
    """For example `us`, `eu`, `apac` or `oc`."""
    limits: UploadLimits
    purchases_remaining_in_window: int | None
    """Agent accounts only, else None."""

    @classmethod
    def from_body(cls, body: object) -> Account:
        check_shape(body, ACCOUNT, "account response")
        fields = as_dict(body) or {}
        limits = as_dict(fields["limits"]) or {}
        return cls(
            _extra=extra_fields(
                fields,
                "balance_seconds",
                "held_seconds",
                "credits_expire_at",
                "card_on_file",
                "data_region",
                "limits",
                "purchases_remaining_in_window",
            ),
            balance_seconds=as_whole(fields["balance_seconds"]),
            held_seconds=as_whole(fields["held_seconds"]),
            credits_expire_at=_expiry(fields),
            card_on_file=as_flag(fields["card_on_file"]),
            data_region=as_text(fields["data_region"]),
            limits=UploadLimits(
                _extra=extra_fields(
                    limits,
                    "max_daily_seconds",
                    "max_active_jobs",
                    "active_jobs",
                    "used_today_seconds",
                ),
                max_daily_seconds=as_whole(limits["max_daily_seconds"]),
                max_active_jobs=as_whole(limits["max_active_jobs"]),
                active_jobs=as_whole(limits["active_jobs"]),
                used_today_seconds=as_whole(limits["used_today_seconds"]),
            ),
            purchases_remaining_in_window=maybe_whole(fields.get("purchases_remaining_in_window")),
        )
