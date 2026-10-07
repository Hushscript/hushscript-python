from __future__ import annotations

import json
import os
from pathlib import Path

import golden_table
import pytest
from golden_table import Golden

from helpers import transcript_body
from hushscript import Transcript, Utterance
from hushscript.format import (
    MAX_CAPTION_CHARS,
    MAX_CAPTION_LINES,
    MAX_CUE_MS,
    cue_text,
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
