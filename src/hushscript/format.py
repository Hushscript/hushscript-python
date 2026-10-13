"""The SRT, VTT and text exporters, byte for byte what the Hushscript app produces (spec 6.2).

The conformance goldens pin the output. JavaScript's rules are kept where they differ from
Python's: its whitespace set, UTF-16 line lengths, `Math.round` rounding.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .transcript import Utterance

MAX_CAPTION_CHARS: Final = 42
MAX_CAPTION_LINES: Final = 2
MAX_CUE_MS: Final = 7000
_ASTRAL: Final = 0x10000
_MS_PER_HOUR: Final = 3_600_000
_MS_PER_MINUTE: Final = 60_000
_SECONDS_PER_HOUR: Final = 3600
_SECONDS_PER_MINUTE: Final = 60

# JavaScript's whitespace (the set `\s` and `String.prototype.trim` use): it has U+FEFF and lacks
# U+0085 and the C0 separators that Python's `str.split()` treats as space.
JS_SPACE: Final = "".join(
    chr(code)
    for code in (
        *(9, 10, 11, 12, 13, 32, 0xA0, 0x1680),
        *range(0x2000, 0x200B),
        *(0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF),
    )
)
_WORD: Final = re.compile(f"[^{re.escape(JS_SPACE)}]+")
# An SRT reader takes a line holding "-->" for a timing line, so a run of dashes before ">" is cut
# to "->" (a plain "-->" swap would turn "--->" back into "-->").
_DASH_ARROW: Final = re.compile(r"-{2,}>")


@dataclass(frozen=True, slots=True)
class Cue:
    start_ms: int
    end_ms: int
    speaker_name: str
    """Empty when the cue carries no speaker prefix."""
    text: str


def js_strip(text: str) -> str:
    return text.strip(JS_SPACE)


def utf16_length(text: str) -> int:
    """The length JavaScript reports for `text`; a lone surrogate counts as one unit."""
    return len(text) + sum(1 for char in text if ord(char) >= _ASTRAL)


def round_half_up(value: float) -> int:
    """`Math.round` for a non-negative value (Python's `round` rounds halves to even)."""
    floor = math.floor(value)
    return floor + 1 if value - floor >= 0.5 else floor  # noqa: PLR2004


def _wrap_state(words: list[str], max_chars: int, max_lines: int) -> list[str]:
    cues: list[str] = []
    lines: list[str] = []
    line = ""
    line_length = 0

    def flush_line() -> None:
        nonlocal line, line_length
        if line:
            lines.append(line)
        line, line_length = "", 0

    def flush_cue() -> None:
        flush_line()
        if lines:
            cues.append("\n".join(lines))
        lines.clear()

    for word in words:
        word_length = utf16_length(word)
        candidate = f"{line} {word}" if line else word
        candidate_length = line_length + 1 + word_length if line else word_length
        if candidate_length <= max_chars:
            line, line_length = candidate, candidate_length
            continue
        flush_line()
        if len(lines) >= max_lines:
            flush_cue()
        line, line_length = word, word_length
    flush_cue()
    return cues


def wrap_into_cues(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Word-wraps `text` into cues of at most `max_lines` lines of `max_chars`; an overlong word
    keeps a line to itself. Text without a word gives one empty cue."""
    words = _WORD.findall(text)
    if not words:
        return [""]
    return _wrap_state(words, max_chars, max_lines) or [""]


def utterance_cues(utterances: Sequence[Utterance]) -> list[Cue]:
    return [Cue(u.start_ms, u.end_ms, u.speaker_name, u.text) for u in utterances]


def segment_captions(utterances: Sequence[Utterance]) -> list[Cue]:
    """Re-cuts utterances into readable cues: lines of at most 42 characters, two lines to a cue,
    the utterance span split by character share, and every cue, the last of an utterance included,
    capped at 7000 ms. Positions come from the cumulative character share, so the cap never shifts
    a later cue."""
    out: list[Cue] = []
    for utterance in utterances:
        chunks = wrap_into_cues(utterance.text, MAX_CAPTION_CHARS, MAX_CAPTION_LINES)
        span = max(0, utterance.end_ms - utterance.start_ms)
        total = sum(utf16_length(chunk) for chunk in chunks) or 1
        accumulated = 0
        for index, text in enumerate(chunks):
            start_ms = utterance.start_ms + round_half_up(span * accumulated / total)
            accumulated += max(1, utf16_length(text))
            end_ms = utterance.end_ms
            if index != len(chunks) - 1:
                end_ms = utterance.start_ms + round_half_up(span * accumulated / total)
            end_ms = min(end_ms, start_ms + MAX_CUE_MS)
            out.append(Cue(start_ms, max(end_ms, start_ms), utterance.speaker_name, text))
    return out


def timestamp(milliseconds: int, separator: str) -> str:
    """`HH:MM:SS,mmm`, floored to whole milliseconds; VTT swaps the comma for a dot."""
    total = max(0, milliseconds)
    hours, rest = divmod(total, _MS_PER_HOUR)
    minutes, rest = divmod(rest, _MS_PER_MINUTE)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def cue_text(text: str) -> str:
    """Keeps a cue's line breaks but drops its blank lines: SRT and VTT end a cue at the first."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line for line in lines if js_strip(line))


def _with_speaker(cue: Cue) -> str:
    return f"{cue.speaker_name}: {cue.text}" if cue.speaker_name else cue.text


def _cues(utterances: Sequence[Utterance], *, captions: bool) -> list[Cue]:
    return segment_captions(utterances) if captions else utterance_cues(utterances)


def render_srt(utterances: Sequence[Utterance], *, captions: bool = True) -> str:
    blocks = [
        f"{number}\n{timestamp(cue.start_ms, ',')} --> {timestamp(cue.end_ms, ',')}\n"
        + _DASH_ARROW.sub("->", cue_text(_with_speaker(cue)))
        for number, cue in enumerate(_cues(utterances, captions=captions), start=1)
    ]
    return "\n\n".join(blocks)


def _vtt_text(text: str) -> str:
    """Escapes what WebVTT reads as markup (`&` and `<`) and as the end of a cue (`-->`)."""
    return cue_text(text).replace("&", "&amp;").replace("<", "&lt;").replace("-->", "--&gt;")


def render_vtt(utterances: Sequence[Utterance], *, captions: bool = True) -> str:
    blocks = [
        f"{number}\n{timestamp(cue.start_ms, '.')} --> {timestamp(cue.end_ms, '.')}\n"
        + _vtt_text(_with_speaker(cue))
        for number, cue in enumerate(_cues(utterances, captions=captions), start=1)
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


@dataclass(slots=True)
class _Block:
    speaker: str
    speaker_name: str
    start_ms: int
    text: str


def _blocks(utterances: Sequence[Utterance], *, merge: bool) -> list[_Block]:
    blocks: list[_Block] = []
    for utterance in utterances:
        if merge and blocks and blocks[-1].speaker == utterance.speaker:
            blocks[-1].text += " " + utterance.text
            continue
        blocks.append(
            _Block(utterance.speaker, utterance.speaker_name, utterance.start_ms, utterance.text)
        )
    return blocks


def _clock(milliseconds: int) -> str:
    """`M:SS` or `H:MM:SS`, floored to whole seconds."""
    seconds = max(0, milliseconds) // 1000
    hours, rest = divmod(seconds, _SECONDS_PER_HOUR)
    minutes, secs = divmod(rest, _SECONDS_PER_MINUTE)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes}:{secs:02d}"


def render_text(
    utterances: Sequence[Utterance],
    *,
    speakers: bool = True,
    timestamps: bool = False,
    merge: bool = True,
) -> str:
    """ "Name: text" blocks joined by a blank line. `\\r` and whitespace-only lines are kept as they
    come, as in the app."""
    out: list[str] = []
    for block in _blocks(utterances, merge=merge):
        prefix = f"[{_clock(block.start_ms)}] " if timestamps else ""
        who = block.speaker_name if speakers else ""
        out.append(f"{prefix}{who}: {block.text}" if who else f"{prefix}{block.text}")
    return "\n\n".join(out)
