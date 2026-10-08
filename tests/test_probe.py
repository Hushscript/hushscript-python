from __future__ import annotations

import io
import math
from typing import TYPE_CHECKING

import pytest

from hushscript import PreflightError, UnsupportedMediaError
from hushscript.transcribe.preflight import Options, check_media
from hushscript.transcribe.probe import probe_duration, scan_mp3_duration
from hushscript.transcribe.sniff import HEAD_BYTES, sniff
from hushscript.transcribe.source import BytesSource, PathSource, make_source
from pipe import media

if TYPE_CHECKING:
    from pathlib import Path

# MPEG-1 Layer III at 44.1 kHz: 1152 samples per frame; 128 kbit/s frames are 417 bytes and
# 192 kbit/s frames are 626.
FRAME_128 = b"\xff\xfb\x90\x00" + bytes(413)
FRAME_192 = b"\xff\xfb\xb0\x00" + bytes(622)
FRAME_SECONDS = 1152 / 44100


class OneWay(io.BytesIO):
    def seekable(self) -> bool:
        return False


def test_every_fixture_is_declared_at_or_above_its_true_duration(
    media_dir: Path, durations: dict[str, float]
) -> None:
    assert len(durations) == 20
    for name, true in durations.items():
        if name == "webm-renamed.mp3":  # R46: refused by the sniffer, never probed
            continue
        got = probe_duration(PathSource(media_dir / name))
        assert math.ceil(got) >= true, name
        assert got - true <= 1, name


def test_a_vbr_mp3_without_a_xing_header_is_scanned_not_estimated(
    media_dir: Path, durations: dict[str, float]
) -> None:
    for name in ("vbr-noxing-20s.mp3", "vbr-noxing-61s.mp3"):
        got = probe_duration(PathSource(media_dir / name))
        assert abs(got - durations[name]) < 0.05, name


def test_the_probe_reads_a_seekable_stream_and_bytes_alike(media_dir: Path) -> None:
    path = media_dir / "flac-20s.flac"
    data = path.read_bytes()
    assert probe_duration(BytesSource(data)) == probe_duration(PathSource(path))
    assert probe_duration(make_source(io.BytesIO(data))) == probe_duration(PathSource(path))


def test_the_scan_sums_every_frame_whatever_its_bitrate() -> None:
    data = FRAME_128 * 30 + FRAME_192 * 20 + FRAME_128 * 10
    assert scan_mp3_duration(io.BytesIO(data)) == pytest.approx(60 * FRAME_SECONDS)


def test_the_scan_skips_an_id3_tag_and_a_trailing_id3v1_tag() -> None:
    tag = b"ID3\x04\x00\x00\x00\x00\x00\x14" + bytes(20)
    data = tag + FRAME_128 * 40 + b"TAG" + bytes(125)
    assert scan_mp3_duration(io.BytesIO(data)) == pytest.approx(40 * FRAME_SECONDS)


def test_the_scan_resyncs_past_garbage_between_frames() -> None:
    data = FRAME_128 * 10 + b"\x00" * 7 + FRAME_128 * 10
    assert scan_mp3_duration(io.BytesIO(data)) == pytest.approx(20 * FRAME_SECONDS)


def test_the_scan_handles_the_mpeg2_frame_size() -> None:
    # MPEG-2 Layer III at 22.05 kHz, 64 kbit/s: 576 samples, 72 * 64000 / 22050 = 208 bytes.
    frame = b"\xff\xf3\x80\x00" + bytes(204)
    assert scan_mp3_duration(io.BytesIO(frame * 50)) == pytest.approx(50 * 576 / 22050)


def test_a_file_with_no_mpeg_frames_has_no_scan() -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        scan_mp3_duration(io.BytesIO(b"\xff\xfb\x00\x00" * 4 + bytes(100_000)))
    assert raised.value.code == "duration_unreadable"


def test_a_webm_renamed_to_mp3_is_refused_not_probed(media_dir: Path) -> None:
    webm = media_dir / "webm-renamed.mp3"
    assert sniff(webm.read_bytes()[:HEAD_BYTES]) is None
    with pytest.raises(UnsupportedMediaError) as raised:
        check_media(PathSource(webm), Options())
    assert raised.value.code == "unsupported_media"
    with pytest.raises(UnsupportedMediaError) as unreadable:
        probe_duration(PathSource(webm))
    assert unreadable.value.code == "duration_unreadable"


@pytest.mark.parametrize(
    "data",
    [
        b"fLaC" + bytes(40),
        b"\x00\x00\x00\x18ftypM4A " + bytes(40),
        b"RIFF\x00\x00\x00\x00WAVE" + bytes(40),
        b"OggS" + bytes(60),
        b"ID3" + bytes(50),
        b"\x1a\x45\xdf\xa3\x00",
        b"\x1a\x45\xdf\xa3\xff",
        b"plain text, not media",
    ],
)
def test_bytes_that_are_not_readable_media_have_no_duration(data: bytes) -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        probe_duration(BytesSource(data))
    assert raised.value.code == "duration_unreadable"
    assert "duration_seconds" in str(raised.value)


@pytest.mark.parametrize(
    ("data", "shown"),
    [
        (b"fLaC" + bytes(40), "error: file said 2 bytes, read 0 bytes"),
        (b"\x00\x00\x00\x18ftypM4A " + bytes(40), "MP4StreamInfoError: not a MP4 file"),
        (b"RIFF\x00\x00\x00\x00WAVE" + bytes(40), "InvalidChunk: Container chunk data size < 4"),
        (b"OggS" + bytes(60), "OggVorbisHeaderError: page has not packets"),
    ],
)
def test_a_probe_failure_names_the_original_type_and_message(data: bytes, shown: str) -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        probe_duration(BytesSource(data))
    assert raised.value.message == f"Could not read the duration ({shown}); pass duration_seconds."


def test_a_stream_that_cannot_seek_cannot_be_probed() -> None:
    source = make_source(OneWay(FRAME_128 * 10), 4170)
    with pytest.raises(UnsupportedMediaError):
        probe_duration(source)


def test_a_file_that_reports_no_length_is_unreadable(media_dir: Path) -> None:
    silent = bytearray((media_dir / "pcm-20s.wav").read_bytes()[:44])
    silent[40:44] = b"\x00\x00\x00\x00"
    with pytest.raises(UnsupportedMediaError):
        probe_duration(BytesSource(bytes(silent)))


class FailingHead(BytesSource):
    """Bytes whose head read fails on the given call."""

    def __init__(self, data: bytes, failing_call: int) -> None:
        super().__init__(data)
        self.failing_call = failing_call
        self.calls = 0

    def head(self) -> bytes:
        self.calls += 1
        if self.calls == self.failing_call:
            raise OSError("disk went away")
        return super().head()


@pytest.mark.parametrize("failing_call", [1, 2])
def test_a_read_failure_in_preflight_names_the_original_and_keeps_the_os_error(
    failing_call: int,
) -> None:
    source = FailingHead(media(), failing_call)
    with pytest.raises(PreflightError) as raised:
        check_media(source, Options())
    assert (raised.value.code, raised.value.message) == (
        "file_unreadable",
        "The file cannot be read (OSError: disk went away).",
    )
    assert source.calls == failing_call
    assert type(raised.value.__cause__) is OSError  # spec 9.2: the OS error is the cause
