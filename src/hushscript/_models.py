from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from ._json import as_dict
from ._response import BadBodyError

if TYPE_CHECKING:
    from collections.abc import Mapping


def _int_field(body: Mapping[str, object], key: str) -> int:
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadBodyError(f"account response (no integer {key})")
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
            raise BadBodyError("account response (not an object)")
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


@dataclass(frozen=True, slots=True)
class UploadingProgress:
    """Bytes the API has acknowledged; `percent` is 0 while the call waits for a create slot."""

    percent: int
    bytes_sent: int
    bytes_total: int
    stage: Literal["uploading"] = "uploading"


@dataclass(frozen=True, slots=True)
class ProcessingProgress:
    """The job's state while it is queued or processing."""

    state: str
    stage: Literal["processing"] = "processing"


Progress = UploadingProgress | ProcessingProgress


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    state: str
    """`uploading`, `fetching`, `queued`, `processing`, `done` or `failed`; an unknown state passes
    through untouched."""
    transcript_id: str | None
    error: str | None
    failure_kind: str | None
    raw: Mapping[str, object]

    @classmethod
    def from_body(cls, body: object) -> Job:
        fields = as_dict(body)
        if fields is None or not isinstance(fields.get("id"), str):
            raise BadBodyError("job response (no id)")
        return cls(
            id=str(fields["id"]),
            state=str(fields.get("state")),
            transcript_id=_text(fields.get("transcript_id")),
            error=_text(fields.get("error")),
            failure_kind=_text(fields.get("failure_kind")),
            raw=fields,
        )


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class Transcript:
    """The transcript as the API returns it. The formatters and typed fields arrive with the
    transcript task; until then `raw` is the body of `GET /v1/transcripts/{id}`."""

    raw: Mapping[str, object]

    @property
    def id(self) -> str:
        return str(self.raw.get("id"))

    def to_json(self) -> Mapping[str, object]:
        return self.raw


def to_transcript(body: object) -> Transcript:
    fields = as_dict(body)
    if fields is None:
        raise BadBodyError("transcript response (not an object)")
    return Transcript(raw=fields)
