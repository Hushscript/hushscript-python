"""The golden files of the conformance suite (`fixtures/exports`) and how each one is rendered.

The golden test and the runner's `format` op share this table, so the two cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from hushscript import Transcript

# The transcript fixtures (`fixtures/transcripts`, without `.json`).
TRANSCRIPTS: Final = (
    "escapes",
    "long-utterances",
    "multi-renamed",
    "no-labels",
    "one-speaker",
    "over-hour",
    "translated",
)
# Only this transcript has translation and cleaned goldens: `<name>.<variant>.<language>.<ext>`.
LANGUAGE_TRANSCRIPT: Final = "translated"
LANGUAGES: Final = ("es", "cleaned")
EXPECTED_COUNT: Final = 72


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    extension: str
    render: Callable[[Transcript, str | None], str]


VARIANTS: Final = (
    Variant("srt-captions", "srt", lambda t, lang: t.to_srt(lang)),
    Variant("srt-plain", "srt", lambda t, lang: t.to_srt(lang, captions=False)),
    Variant("vtt-captions", "vtt", lambda t, lang: t.to_vtt(lang)),
    Variant("vtt-plain", "vtt", lambda t, lang: t.to_vtt(lang, captions=False)),
    Variant("txt-default", "txt", lambda t, lang: t.to_text(lang)),
    Variant("txt-nospeakers", "txt", lambda t, lang: t.to_text(lang, speakers=False)),
    Variant("txt-timestamps", "txt", lambda t, lang: t.to_text(lang, timestamps=True)),
    Variant("txt-nomerge", "txt", lambda t, lang: t.to_text(lang, merge=False)),
)


@dataclass(frozen=True, slots=True)
class Golden:
    file: str
    """The name under `fixtures/exports`."""
    transcript: str
    """The fixture under `fixtures/transcripts`, without `.json`."""
    language: str | None
    variant: Variant

    def render(self, transcript: Transcript) -> str:
        return self.variant.render(transcript, self.language)


def all_goldens() -> list[Golden]:
    """Every golden from the naming scheme `<transcript>.<variant>[.<language>].<ext>`."""
    out: list[Golden] = []
    for transcript in TRANSCRIPTS:
        languages: list[str | None] = [None]
        if transcript == LANGUAGE_TRANSCRIPT:
            languages += LANGUAGES
        for variant in VARIANTS:
            for language in languages:
                middle = f".{language}" if language else ""
                name = f"{transcript}.{variant.name}{middle}.{variant.extension}"
                out.append(Golden(name, transcript, language, variant))
    return out
