from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from typing import Final

from hushscript._errors import ConfigurationError, ResumeMismatchError
from hushscript._json import as_dict

from .source import FileInput, Source, make_source, path_size

TOKEN_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class ResumeState:
    job_id: str
    idempotency_key: str
    size: int
    duration_seconds: int


def encode_token(state: ResumeState) -> str:
    """The opaque resume token: base64url of `{v, jobId, idempotencyKey, size, durationSeconds}`
    (spec 6.1), the same bytes in every SDK."""
    payload = {
        "v": TOKEN_VERSION,
        "jobId": state.job_id,
        "idempotencyKey": state.idempotency_key,
        "size": state.size,
        "durationSeconds": state.duration_seconds,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def decode_token(token: str) -> ResumeState:
    invalid = ConfigurationError("This is not a resume token from this SDK.")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        fields = as_dict(json.loads(raw))
    except (ValueError, binascii.Error) as failure:
        raise invalid from failure
    if fields is None or fields.get("v") != TOKEN_VERSION:
        raise invalid
    job_id = fields.get("jobId")
    key = fields.get("idempotencyKey")
    size = _whole(fields.get("size"))
    duration = _whole(fields.get("durationSeconds"))
    if not isinstance(job_id, str) or not isinstance(key, str) or size is None or duration is None:
        raise invalid
    return ResumeState(job_id=job_id, idempotency_key=key, size=size, duration_seconds=duration)


def check_same_file(state: ResumeState, size: int) -> None:
    """A replay with a different file silently returns the old job (spec 7.3), so it is refused
    before any request."""
    if size != state.size:
        raise ResumeMismatchError(
            f"The file is {size} bytes; the upload started with {state.size}.",
            code="resume_file_mismatch",
        )


def early_source(state: ResumeState, file: FileInput | None) -> Source | None:
    """The source of a resume's file, when it can be had before any request. A path is only sized
    (a different size is refused now) and opened later, once the job is known to be `uploading`
    (spec 7.3)."""
    if file is None:
        return None
    if isinstance(file, (str, os.PathLike)):
        size = path_size(file)
        if size is not None:
            check_same_file(state, size)
        return None
    source = make_source(file)
    check_same_file(state, source.size)
    return source


def late_source(state: ResumeState, file: FileInput | None, source: Source | None) -> Source:
    """The source for the upload a resume has to finish."""
    if source is not None:
        return source
    if file is None:
        raise file_required()
    opened = make_source(file)
    check_same_file(state, opened.size)
    return opened


def file_required() -> ResumeMismatchError:
    return ResumeMismatchError(
        "The upload was not finished and no file was given.", code="resume_file_required"
    )


def job_missing() -> ResumeMismatchError:
    return ResumeMismatchError(
        "The job behind this resume token no longer exists.", code="resume_job_missing"
    )
