from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ._json import as_dict, as_list
from ._shape import (
    as_flag,
    as_text,
    check_shape,
    maybe_flag,
    maybe_text,
    maybe_whole,
    to_datetime,
)
from ._shapes import JOB

if TYPE_CHECKING:
    from datetime import datetime


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
class JobOptions:
    """What the job was submitted with, from the API's content-free summary: it says whether
    keyterms and a prompt were set, never what they were. A key the API adds later is not kept
    here; `hs.api` returns the whole body."""

    language_code: str | None
    """The forced language, or None when it was auto-detected."""
    speaker_detection: bool
    medical_mode: bool
    multichannel: bool
    translation_targets: list[str]
    keyterms: bool
    prompt: bool
    auto_generate_insights: bool | None
    """The upload's insights override, or None when it used the account default."""


@dataclass(frozen=True, slots=True)
class Job:
    """A processing job (spec 6.4). The private-result and from-URL fetch fields are left out;
    `hs.api` still returns them."""

    id: str
    state: str
    """`uploading`, `fetching`, `queued`, `processing`, `done` or `failed`; a state the SDK does
    not know yet passes through as the API's own string."""
    transcript_id: str | None
    error: str | None
    """The failure text of a failed job; opaque."""
    failure_kind: str | None
    """`media_unreadable` or `media_undecodable` when the file itself could not be read."""
    mode: str
    declared_seconds: int | None
    verified_seconds: int | None
    actual_seconds: int | None
    billable_seconds: int | None
    retry_of: str | None
    created_at: datetime
    options: JobOptions

    @classmethod
    def from_body(cls, body: object) -> Job:
        check_shape(body, JOB, "job response")
        fields = as_dict(body) or {}
        options = as_dict(fields["options"]) or {}
        return cls(
            id=as_text(fields["id"]),
            state=as_text(fields["state"]),
            transcript_id=maybe_text(fields["transcript_id"]),
            error=maybe_text(fields["error"]),
            failure_kind=maybe_text(fields["failure_kind"]),
            mode=as_text(fields["mode"]),
            declared_seconds=maybe_whole(fields["declared_seconds"]),
            verified_seconds=maybe_whole(fields["verified_seconds"]),
            actual_seconds=maybe_whole(fields["actual_seconds"]),
            billable_seconds=maybe_whole(fields["billable_seconds"]),
            retry_of=maybe_text(fields["retry_of"]),
            created_at=to_datetime(fields["created_at"]),
            options=JobOptions(
                language_code=maybe_text(options["language_code"]),
                speaker_detection=as_flag(options["speaker_detection"]),
                medical_mode=as_flag(options["medical_mode"]),
                multichannel=as_flag(options["multichannel"]),
                translation_targets=[
                    as_text(t) for t in as_list(options["translation_targets"]) or []
                ],
                keyterms=as_flag(options["keyterms"]),
                prompt=as_flag(options["prompt"]),
                auto_generate_insights=maybe_flag(options["auto_generate_insights"]),
            ),
        )
