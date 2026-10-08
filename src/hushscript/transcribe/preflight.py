from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from hushscript._errors import (
    DailyLimitError,
    FileLimitError,
    PreflightError,
    UnsupportedMediaError,
    describe_failure,
)
from hushscript._json import as_dict
from hushscript._shape import INT_LIMIT

from .probe import probe_duration
from .sniff import sniff

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .source import Source

MAX_BYTES: Final = 5_000_000_000
MIN_SECONDS: Final = 15
MAX_SECONDS: Final = 36_000
MAX_CONCURRENCY: Final = 8
MAX_KEYTERMS: Final = 1000
MAX_KEYTERM_WORDS: Final = 6
MAX_MATTER_CODE: Final = 64
MEDICAL_LANGUAGES: Final = frozenset({"en", "es", "fr", "de"})
KEY_MIN: Final = 16
KEY_MAX: Final = 128
_PRINTABLE_FIRST: Final = 0x21
_PRINTABLE_LAST: Final = 0x7E


def invalid_option(message: str) -> PreflightError:
    return PreflightError(message, code="invalid_option")


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def check_wait_timeout(wait_timeout: object) -> None:
    if not _is_number(wait_timeout) or cast("float", wait_timeout) <= 0:
        raise invalid_option("wait_timeout must be a positive number of seconds.")


@dataclass(frozen=True, slots=True)
class Options:
    """The options of `transcribe()` (spec 6.1), checked before any request."""

    title: str | None = None
    language: str | None = None
    speakers: bool = True
    translate_to: tuple[str, ...] = ()
    keyterms: tuple[str, ...] = ()
    prompt: str | None = None
    medical: bool = False
    multichannel: bool = False
    auto_insights: bool | None = None
    matter_code: str | None = None
    duration_seconds: float | None = None
    idempotency_key: str | None = None
    concurrency: int = 4
    wait_timeout: float = 3600

    def validate(self) -> Options:
        concurrency = cast("object", self.concurrency)
        if (
            not isinstance(concurrency, int)
            or isinstance(concurrency, bool)
            or not 1 <= concurrency <= MAX_CONCURRENCY
        ):
            raise invalid_option(f"concurrency must be a whole number from 1 to {MAX_CONCURRENCY}.")
        check_wait_timeout(self.wait_timeout)
        if self.duration_seconds is not None and (
            not _is_number(self.duration_seconds) or self.duration_seconds <= 0
        ):
            raise invalid_option("duration_seconds must be a positive number of seconds.")
        key = cast("object", self.idempotency_key)
        if key is not None and not (
            isinstance(key, str)
            and KEY_MIN <= len(key) <= KEY_MAX
            and all(_PRINTABLE_FIRST <= ord(char) <= _PRINTABLE_LAST for char in key)
        ):
            raise invalid_option(
                f"idempotency_key must be {KEY_MIN} to {KEY_MAX} visible ASCII characters,"
                " no spaces."
            )
        if self.medical and self.language not in MEDICAL_LANGUAGES:
            raise invalid_option("medical needs language to be one of en, es, fr, de.")
        if len(self.keyterms) > MAX_KEYTERMS or any(
            len(term.split()) > MAX_KEYTERM_WORDS for term in self.keyterms
        ):
            raise invalid_option(
                f"keyterms takes up to {MAX_KEYTERMS} terms of at most {MAX_KEYTERM_WORDS} words."
            )
        if self.matter_code is not None and len(self.matter_code) > MAX_MATTER_CODE:
            raise invalid_option(f"matter_code must be at most {MAX_MATTER_CODE} characters.")
        return self

    def new_key(self) -> str:
        return self.idempotency_key or str(uuid.uuid4())

    def transcription_options(self) -> dict[str, object]:
        wire: dict[str, object] = {}
        if self.language is not None:
            wire["language_code"] = self.language
        if not self.speakers and not self.translate_to:
            wire["speaker_detection"] = False
        if self.translate_to:
            wire["translation_targets"] = list(self.translate_to)
        if self.keyterms:
            wire["keyterms_prompt"] = list(self.keyterms)
        if self.prompt is not None:
            wire["prompt"] = self.prompt
        if self.medical:
            wire["medical_mode"] = True
        if self.multichannel:
            wire["multichannel"] = True
        if self.auto_insights is not None:
            wire["auto_generate_insights"] = self.auto_insights
        return wire


@dataclass(frozen=True, slots=True)
class Media:
    size: int
    duration_seconds: int
    """The declared duration: `ceil` of the probe, so the hold never falls short of the file."""


def check_media(source: Source, options: Options) -> Media:
    """Spec 8.1 steps 1 to 3: format by magic bytes, size, duration."""
    if source.sequential and options.duration_seconds is None:
        raise invalid_option("A stream that cannot seek needs duration_seconds and size.")
    try:
        head = source.head()
    except OSError as failure:
        raise PreflightError(
            f"The file cannot be read ({describe_failure(failure)}).", code="file_unreadable"
        ) from failure
    if sniff(head) is None:
        raise UnsupportedMediaError("The file is not a supported audio or video format.")
    if not 1 <= source.size <= MAX_BYTES:
        raise FileLimitError(
            f"The file is {source.size} bytes; it must be between 1 byte and 5 GB.",
            code="size_out_of_range",
        )
    seconds = options.duration_seconds
    if seconds is None:
        try:
            seconds = probe_duration(source)
        except OSError as failure:
            raise PreflightError(
                f"The file cannot be read ({describe_failure(failure)}).", code="file_unreadable"
            ) from failure
    declared = math.ceil(seconds)
    if seconds < MIN_SECONDS or declared > MAX_SECONDS:
        raise FileLimitError(
            f"The file is {seconds:g} seconds long; it must be between 15 seconds and 10 hours.",
            code="duration_out_of_range",
        )
    return Media(size=source.size, duration_seconds=declared)


def _whole(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) < INT_LIMIT
        else None
    )


def check_account(account: object, media: Media) -> None:
    """Spec 8.1 step 5, from one `GET /v1/account`: the daily limit only.

    The balance is the server's to judge at create (R77).
    """
    fields = as_dict(account) or {}
    limits = as_dict(fields.get("limits")) or {}
    daily = _whole(limits.get("max_daily_seconds"))
    used = _whole(limits.get("used_today_seconds"))
    if daily is not None and used is not None and used + media.duration_seconds > daily:
        raise DailyLimitError(
            "This upload would pass the daily transcription limit.",
            code="daily_limit",
            details={"used_today_seconds": used, "max_daily_seconds": daily},
        )


def create_body(
    media: Media, options: Options, key: str, *, title: str | None
) -> Mapping[str, object]:
    body: dict[str, object] = {
        "size_bytes": media.size,
        "duration_seconds": media.duration_seconds,
        "idempotency_key": key,
    }
    if title is not None:
        body["title"] = title
    if options.matter_code is not None:
        body["matter_code"] = options.matter_code
    wire = options.transcription_options()
    if wire:
        body["transcription_options"] = wire
    return body
