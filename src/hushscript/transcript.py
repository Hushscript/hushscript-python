from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from ._json import as_dict, as_list
from ._response import BadBodyError
from ._shape import (
    as_flag,
    as_text,
    as_whole,
    check_shape,
    maybe_text,
    to_datetime,
)
from ._shapes import TRANSCRIPT_DETAIL
from .format import js_strip, render_srt, render_text, render_vtt

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

CLEANED: Final = "cleaned"
"""The reserved translation key that holds the AI-cleaned body."""


@dataclass(frozen=True, slots=True)
class Utterance:
    speaker: str
    """The provider's raw label; empty for a transcript without speaker labels."""
    speaker_name: str
    """The saved name, else `Speaker {label}`, else empty for an empty label."""
    start_ms: int
    end_ms: int
    text: str


def display_name(label: str, names: Mapping[str, str]) -> str:
    saved = js_strip(names.get(label, ""))
    if saved:
        return saved
    return "" if not js_strip(label) else f"Speaker {label}"


def _utterances(language: object, names: Mapping[str, str]) -> list[Utterance]:
    body = as_dict(language) or {}
    out: list[Utterance] = []
    for item in as_list(body.get("utterances")) or []:
        fields = as_dict(item) or {}
        speaker = as_text(fields["speaker"])
        out.append(
            Utterance(
                speaker=speaker,
                speaker_name=display_name(speaker, names),
                start_ms=_milliseconds(fields["start_ms"]),
                end_ms=_milliseconds(fields["end_ms"]),
                text=as_text(fields["text"]),
            )
        )
    return out


def _milliseconds(value: object) -> int:
    """Whole milliseconds, floored: the app's timestamps are."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BadBodyError("a number of milliseconds")
    return math.floor(value)


@dataclass(frozen=True, slots=True, repr=False)
class Transcript:
    """A finished transcript with its formatters (spec 6.2). `to_json()` is the API's body."""

    id: str
    title: str
    language: str | None
    duration_seconds: int
    created_at: datetime
    updated_at: datetime
    auto_delete_at: datetime | None
    tags: list[str]
    edited: bool
    speakers: dict[str, str]
    """Label to display name, for the speakers that were renamed."""
    utterances: list[Utterance]
    """The original language."""
    languages: list[str]
    """The translation locales, without the reserved `cleaned`, in the API's order."""
    cleaned: list[Utterance] | None
    """The AI-cleaned body, when there is one."""
    _raw: Mapping[str, object] = field(repr=False, compare=False)
    _translations: Mapping[str, list[Utterance]] = field(repr=False, compare=False)

    @classmethod
    def from_api(cls, body: object) -> Transcript:
        """Builds a transcript from a `GET /v1/transcripts/{id}` body; one that does not fit raises
        BadBodyError, which the client reports as `bad_response`."""
        check_shape(body, TRANSCRIPT_DETAIL, "transcript response")
        fields = as_dict(body) or {}
        names = {
            key: as_text(value) for key, value in (as_dict(fields["speaker_names"]) or {}).items()
        }
        envelope = as_dict(fields["body"]) or {}
        translations = {
            locale: _utterances(language, names)
            for locale, language in (as_dict(envelope["translations"]) or {}).items()
        }
        auto_delete = fields["auto_delete_at"]
        return cls(
            id=as_text(fields["id"]),
            title=as_text(fields["title"]),
            language=maybe_text(fields["language_detected"]),
            duration_seconds=as_whole(fields["duration_seconds"]),
            created_at=to_datetime(fields["created_at"]),
            updated_at=to_datetime(fields["updated_at"]),
            auto_delete_at=None if auto_delete is None else to_datetime(auto_delete),
            tags=[as_text(tag) for tag in as_list(fields["tags"]) or []],
            edited=as_flag(fields["edited"]),
            speakers=names,
            utterances=_utterances(envelope["original"], names),
            languages=[locale for locale in translations if locale != CLEANED],
            cleaned=translations.get(CLEANED),
            _raw=fields,
            _translations=translations,
        )

    @property
    def text(self) -> str:
        """The plain text, the same as `to_text()`."""
        return self.to_text()

    def utterances_for(self, language: str | None = None) -> list[Utterance]:
        """The translation (or `cleaned` body) for `language`; the original when `language` is
        empty or the transcript has no such translation."""
        if language is None:
            return self.utterances
        return self._translations.get(language, self.utterances)

    def to_srt(self, language: str | None = None, *, captions: bool = True) -> str:
        return render_srt(self.utterances_for(language), captions=captions)

    def to_vtt(self, language: str | None = None, *, captions: bool = True) -> str:
        return render_vtt(self.utterances_for(language), captions=captions)

    def to_text(
        self,
        language: str | None = None,
        *,
        speakers: bool = True,
        timestamps: bool = False,
        merge: bool = True,
    ) -> str:
        return render_text(
            self.utterances_for(language), speakers=speakers, timestamps=timestamps, merge=merge
        )

    def to_json(self) -> Mapping[str, object]:
        """The API body this transcript was built from, unknown fields included."""
        return self._raw

    def __repr__(self) -> str:
        return (
            f"Transcript(id={self.id!r}, duration_seconds={self.duration_seconds!r}, "
            f"language={self.language!r})"
        )
