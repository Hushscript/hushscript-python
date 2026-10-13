from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hushscript.transcribe.sniff import HEAD_BYTES, sniff

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED = {
    ".mp3": "mp3",
    ".m4a": "isobmff",
    ".mp4": "isobmff",
    ".wav": "wav",
    ".flac": "flac",
    ".ogg": "ogg",
    ".opus": "ogg",
}


@given(st.binary(max_size=64))
def test_sniff_never_raises_on_arbitrary_bytes(head: bytes) -> None:
    assert sniff(head) in {None, "mp3", "isobmff", "wav", "flac", "ogg"}


def test_every_media_fixture_is_recognized_by_its_bytes(media_dir: Path) -> None:
    checked = 0
    for path in sorted(media_dir.iterdir()):
        if path.suffix not in EXPECTED or path.name in {"webm-renamed.mp3", "truncated.flac"}:
            continue
        assert sniff(path.read_bytes()[:HEAD_BYTES]) == EXPECTED[path.suffix], path.name
        checked += 1
    assert checked == 19


def test_a_webm_renamed_to_mp3_is_not_an_mp3(media_dir: Path) -> None:
    assert sniff((media_dir / "webm-renamed.mp3").read_bytes()[:HEAD_BYTES]) is None


def test_a_truncated_flac_is_still_a_flac_by_its_magic(media_dir: Path) -> None:
    assert sniff((media_dir / "truncated.flac").read_bytes()[:HEAD_BYTES]) == "flac"


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"", None),
        (b"\xff", None),
        (b"\xff\xfb\x90\x00", "mp3"),
        (b"\xff\xe0", "mp3"),
        (b"ID3\x04", "mp3"),
        (b"\x00\x00\x00\x18ftypM4A ", "isobmff"),
        (b"\x00\x00\x00\x18ftyp", None),
        (b"RIFF\x00\x00\x00\x00WAVE", "wav"),
        (b"RF64\x00\x00\x00\x00WAVE", "wav"),
        (b"RIFF\x00\x00\x00\x00AVI ", None),
        (b"fLaC", "flac"),
        (b"OggS", "ogg"),
        (b"\x1a\x45\xdf\xa3", None),
        (b"%PDF-1.7", None),
    ],
)
def test_sniff_by_magic_bytes(head: bytes, expected: str | None) -> None:
    assert sniff(head) == expected
