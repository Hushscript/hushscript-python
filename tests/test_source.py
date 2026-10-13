from __future__ import annotations

import io
from typing import TYPE_CHECKING, cast

import pytest

from hushscript import PreflightError, UploadError
from hushscript.transcribe.source import (
    BytesSource,
    PathSource,
    SequentialSource,
    make_source,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO

DATA = bytes(range(256)) * 100


class OneWay(io.BytesIO):
    """A stream that cannot seek, like a pipe or a socket."""

    def seekable(self) -> bool:
        return False


def test_a_path_is_read_in_ranges(tmp_path: Path) -> None:
    path = tmp_path / "a.bin"
    path.write_bytes(DATA)
    for given in (str(path), path):
        source = make_source(given)
        assert isinstance(source, PathSource)
        assert source.size == len(DATA)
        assert source.read_range(300, 50) == DATA[300:350]
        assert source.head() == DATA[:4096]
        with source.probe_file() as handle:
            assert handle is not None
            assert handle.read(3) == DATA[:3]


def test_bytes_are_read_in_ranges() -> None:
    for given in (DATA, bytearray(DATA), memoryview(DATA)):
        source = make_source(given)
        assert isinstance(source, BytesSource)
        assert source.read_range(10, 5) == DATA[10:15]
        assert source.read_range(len(DATA) - 2, 10) == DATA[-2:]
        with source.probe_file() as handle:
            assert handle is not None
            assert handle.read() == DATA


def test_a_seekable_stream_is_measured_and_read_in_ranges() -> None:
    stream = io.BytesIO(DATA)
    source = make_source(stream)
    assert source.size == len(DATA)
    assert not source.sequential
    assert source.read_range(256, 4) == DATA[256:260]
    assert source.read_range(0, 4) == DATA[:4]
    with source.probe_file() as handle:
        assert handle is stream
        assert stream.tell() == 0


def test_a_seekable_stream_takes_the_size_it_is_given() -> None:
    assert make_source(io.BytesIO(DATA), 77).size == 77


def test_a_stream_that_cannot_seek_needs_its_size() -> None:
    with pytest.raises(PreflightError) as raised:
        make_source(OneWay(DATA))
    assert raised.value.code == "invalid_option"


def test_a_stream_that_cannot_seek_is_read_once_in_order() -> None:
    source = make_source(OneWay(DATA), len(DATA))
    assert isinstance(source, SequentialSource)
    assert source.sequential
    assert source.head() == DATA[:4096]
    assert source.head() == DATA[:4096]
    with source.probe_file() as handle:
        assert handle is None
    assert source.read_range(0, 5000) == DATA[:5000]
    assert source.read_range(5000, 7000) == DATA[5000:12000]
    assert source.read_range(12000, 100000) == DATA[12000:]


def test_a_sequential_part_inside_the_head_is_served_from_it() -> None:
    source = SequentialSource(OneWay(DATA), len(DATA))
    assert source.read_range(0, 100) == DATA[:100]
    assert source.read_range(100, 100) == DATA[100:200]


def test_a_stream_cannot_be_read_out_of_order() -> None:
    source = SequentialSource(OneWay(DATA), len(DATA))
    source.read_range(0, 10)
    with pytest.raises(UploadError) as raised:
        source.read_range(5000, 10)
    assert raised.value.code == "stream_not_seekable"


class Trickle:
    """A stream whose reads come up short without the stream being at its end, as a raw unbuffered
    stream (a pipe, `io.FileIO`) may: every read returns at most `chunk` bytes."""

    def __init__(self, data: bytes, chunk: int, *, seekable: bool) -> None:
        self._data = io.BytesIO(data)
        self._chunk = chunk
        self._seekable = seekable

    def read(self, size: int = -1) -> bytes:
        return self._data.read(self._chunk if size < 0 else min(size, self._chunk))

    def seekable(self) -> bool:
        return self._seekable

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._data.seek(offset, whence)


def _trickle(chunk: int, *, seekable: bool) -> BinaryIO:
    return cast("BinaryIO", Trickle(DATA, chunk, seekable=seekable))


def test_a_stream_that_returns_short_reads_is_not_taken_for_ended() -> None:
    source = make_source(_trickle(7, seekable=False), len(DATA))
    assert isinstance(source, SequentialSource)
    assert source.head() == DATA[:4096]
    assert source.read_range(0, 5000) == DATA[:5000]
    assert source.read_range(5000, 5000) == DATA[5000:10000]
    assert source.read_range(10000, len(DATA)) == DATA[10000:]
    assert source.at_end()


def test_a_seekable_stream_with_short_reads_is_read_to_the_end_of_each_range() -> None:
    source = make_source(_trickle(11, seekable=True))
    assert source.size == len(DATA)
    assert source.read_range(100, 3000) == DATA[100:3100]
    assert source.read_range(len(DATA) - 5, 50) == DATA[-5:]
