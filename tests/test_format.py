from __future__ import annotations

import itertools
import json
import os
import re
from pathlib import Path

import golden_table
import pytest
from golden_table import Golden
from hypothesis import given
from hypothesis import strategies as st

from helpers import transcript_body
from hushscript import Transcript, Utterance
from hushscript.format import (
    MAX_CAPTION_CHARS,
    MAX_CAPTION_LINES,
    MAX_CUE_MS,
    cue_text,
    render_text,
    round_half_up,
    segment_captions,
    timestamp,
    utf16_length,
    wrap_into_cues,
)

GOLDENS = golden_table.all_goldens()


def conformance_dir() -> Path:
    directory = os.environ.get("CONFORMANCE_DIR")
    if not directory:
        pytest.fail("CONFORMANCE_DIR must point at a hushscript-sdk-conformance checkout")
    return Path(directory)


def read(*parts: str) -> str:
    # Bytes, not read_text: universal newlines would turn the escapes goldens' \r into \n.
    return conformance_dir().joinpath(*parts).read_bytes().decode("utf-8")


def transcript(name: str) -> Transcript:
    return Transcript.from_api(json.loads(read("fixtures", "transcripts", f"{name}.json")))


def utterance(
    text: str, start_ms: int = 0, end_ms: int = 10_000, speaker_name: str = ""
) -> Utterance:
    return Utterance("A" if speaker_name else "", speaker_name, start_ms, end_ms, text)


def test_the_golden_list_is_exactly_what_the_suite_ships() -> None:
    scenario = json.loads(read("scenarios", "format-goldens.json"))
    checked = scenario["expect"]["result"]["checked"]
    listed = sorted(golden.file for golden in GOLDENS)
    assert len(listed) == checked == golden_table.EXPECTED_COUNT == 72
    assert len(set(listed)) == len(listed)
    shipped = sorted(path.name for path in (conformance_dir() / "fixtures/exports").iterdir())
    assert listed == shipped
    fixtures = sorted(path.stem for path in (conformance_dir() / "fixtures/transcripts").iterdir())
    assert fixtures == sorted(golden_table.TRANSCRIPTS)


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda golden: golden.file)
def test_every_golden_is_reproduced_byte_for_byte(golden: Golden) -> None:
    assert golden.render(transcript(golden.transcript)) == read("fixtures", "exports", golden.file)


def test_the_escapes_goldens_keep_a_carriage_return() -> None:
    assert "\r" in read("fixtures", "exports", "escapes.txt-default.txt")


def test_the_length_of_a_line_is_counted_in_utf16_code_units() -> None:
    emoji = "\U0001f600"
    assert utf16_length(emoji) == 2
    assert utf16_length("a\ud800b") == 3  # a lone surrogate is one unit and must not raise
    line = emoji * 21  # 42 units: one line
    assert wrap_into_cues(line, MAX_CAPTION_CHARS, MAX_CAPTION_LINES) == [line]
    assert wrap_into_cues(f"{line} x", MAX_CAPTION_CHARS, MAX_CAPTION_LINES) == [f"{line}\nx"]
    # 22 emoji are 44 units: an overlong word keeps a line to itself.
    assert wrap_into_cues(emoji * 22, MAX_CAPTION_CHARS, MAX_CAPTION_LINES) == [emoji * 22]


def test_an_astral_line_wraps_by_units_not_code_points() -> None:
    emoji = "\U0001f600"
    cues = segment_captions([utterance(" ".join([emoji] * 30))])
    assert all(
        utf16_length(line) <= MAX_CAPTION_CHARS for cue in cues for line in cue.text.split("\n")
    )
    assert len(cues) > 1


def test_every_cue_is_capped_at_7000_ms_the_last_one_too() -> None:
    cues = segment_captions([utterance("word " * 8, 0, 60_000)])
    assert [cue.end_ms - cue.start_ms for cue in cues] == [MAX_CUE_MS]
    long = segment_captions([utterance("lorem ipsum " * 40, 0, 600_000)])
    assert len(long) > 1
    assert all(cue.end_ms - cue.start_ms <= MAX_CUE_MS for cue in long)


def test_rounding_is_half_up_not_half_even() -> None:
    assert [round_half_up(x) for x in (0.5, 1.5, 2.5, 2.4999, 3.5)] == [1, 2, 3, 2, 4]


def test_whitespace_is_the_javascript_set() -> None:
    # U+0085 and U+001C are Python spaces but not JavaScript's; U+FEFF is the reverse.
    assert wrap_into_cues("a\u0085b", 42, 2) == ["a\u0085b"]
    assert wrap_into_cues("a\x1cb", 42, 2) == ["a\x1cb"]
    assert wrap_into_cues("a\ufeffb", 42, 2) == ["a b"]
    assert cue_text("one\n　\ntwo") == "one\ntwo"
    assert cue_text("x\v\ny") == "x\v\ny"  # \v is not a line break here


def test_a_timestamp_floors_and_clamps_and_pads_the_hours() -> None:
    assert timestamp(3_723_456, ",") == "01:02:03,456"
    assert timestamp(-5, ".") == "00:00:00.000"
    assert timestamp(360_000_000, ",") == "100:00:00,000"


def test_an_arrow_in_the_text_cannot_make_a_timing_line() -> None:
    body = transcript_body()
    body["body"] = {
        "version": 1,
        "original": {
            "utterances": [
                {"speaker": "", "start_ms": 0, "end_ms": 1000, "text": "a --> b ---> c <i> & d"}
            ]
        },
        "translations": {},
    }
    t = Transcript.from_api(body)
    assert t.to_srt() == "1\n00:00:00,000 --> 00:00:01,000\na -> b -> c <i> & d"
    assert t.to_vtt() == (
        "WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\na --&gt; b ---&gt; c &lt;i> &amp; d\n"
    )


@given(
    text=st.text(alphabet="abc <>-&\n\r😀", min_size=1, max_size=100),
    start=st.integers(min_value=0, max_value=360_000_000),
    duration=st.integers(min_value=0, max_value=100_000),
)
def test_uncaptioned_exports_preserve_text_and_escape_markup(
    text: str, start: int, duration: int
) -> None:
    def clock(ms: int, separator: str) -> str:
        hours = ms // 3_600_000
        minutes = ms // 60_000 % 60
        seconds = ms // 1000 % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{ms % 1000:03d}"

    body = transcript_body()
    body["body"] = {
        "original": {
            "utterances": [
                {"speaker": "", "start_ms": start, "end_ms": start + duration, "text": text}
            ]
        },
        "translations": {},
    }
    result = Transcript.from_api(body)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    clean = "\n".join(line for line in lines if line.strip(" \t"))
    assert result.to_srt(captions=False) == (
        f"1\n{clock(start, ',')} --> {clock(start + duration, ',')}\n"
        + re.sub(r"-{2,}>", "->", clean)
    )
    assert result.to_vtt(captions=False) == (
        f"WEBVTT\n\n1\n{clock(start, '.')} --> {clock(start + duration, '.')}\n"
        + clean.replace("&", "&amp;").replace("<", "&lt;").replace("-->", "--&gt;")
        + "\n"
    )
    assert result.to_text(speakers=False, merge=False) == text


@given(
    words=st.lists(st.text(alphabet="abc😀", min_size=1, max_size=50), min_size=1, max_size=50),
    start=st.integers(min_value=0, max_value=1_000_000),
    duration=st.integers(min_value=1, max_value=600_000),
)
def test_caption_cues_preserve_words_and_enforce_readability(
    words: list[str], start: int, duration: int
) -> None:
    cues = segment_captions([utterance(" \n ".join(words), start, start + duration, "Dana")])
    assert " ".join(cue.text.replace("\n", " ") for cue in cues).split() == words
    assert cues[0].start_ms == start
    assert all(cue.speaker_name == "Dana" for cue in cues)
    assert all(start <= cue.start_ms <= cue.end_ms <= start + duration for cue in cues)
    assert all(cue.end_ms - cue.start_ms <= 7000 for cue in cues)
    assert [cue.start_ms for cue in cues] == sorted(cue.start_ms for cue in cues)
    assert all(left.end_ms <= right.start_ms for left, right in itertools.pairwise(cues))
    for cue in cues:
        lines = cue.text.split("\n")
        assert len(lines) <= 2
        for line in lines:
            units = len(line.encode("utf-16-le")) // 2
            assert units <= 42 or len(line.split()) == 1


@given(
    labels=st.lists(st.sampled_from(["A", "B", ""]), min_size=1, max_size=30),
)
def test_text_merges_only_consecutive_equal_raw_speakers(labels: list[str]) -> None:
    rows = [
        Utterance(label, "Dana" if label else "", 0, 1000, str(i)) for i, label in enumerate(labels)
    ]
    groups: list[tuple[str, list[str]]] = []
    for label, group in itertools.groupby(enumerate(labels), key=lambda pair: pair[1]):
        groups.append((label, [str(i) for i, _ in group]))
    assert render_text(rows) == "\n\n".join(
        ("Dana: " if label else "") + " ".join(words) for label, words in groups
    )
    assert render_text(rows, speakers=False, merge=False) == "\n\n".join(
        str(i) for i in range(len(labels))
    )
