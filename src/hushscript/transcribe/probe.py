from __future__ import annotations

import math
import os
import struct
from typing import TYPE_CHECKING, BinaryIO, Final, Protocol, cast

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.mp3 import MP3, BitrateMode
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from hushscript._errors import UnsupportedMediaError

from .sniff import MediaFormat, sniff

if TYPE_CHECKING:
    from collections.abc import Callable

    from .source import Source

_OPUS_RATE: Final = 48000
_OPUS_PRE_SKIP_OFFSET: Final = 10
_MPEG1: Final = 3
_MPEG2: Final = 2
_MPEG25: Final = 0
_LAYER3: Final = 1
_BITRATES: Final = {
    _MPEG1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    _MPEG2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}
_SAMPLE_RATES: Final = {
    _MPEG1: (44100, 48000, 32000),
    _MPEG2: (22050, 24000, 16000),
    _MPEG25: (11025, 12000, 8000),
}
_ID3_HEADER: Final = 10
_RESYNC_LIMIT: Final = 64 * 1024
_FRAME_HEADER: Final = 4
_SYNC_BYTE: Final = 0xFF
_SYNC_BITS: Final = 0xE0
_FIELD_MASK: Final = 3
_RESERVED_RATE: Final = 3


def _unreadable(reason: str) -> UnsupportedMediaError:
    return UnsupportedMediaError(
        f"Could not read the duration ({reason}); pass duration_seconds.",
        code="duration_unreadable",
    )


def _id3_size(handle: BinaryIO) -> int:
    handle.seek(0)
    head = handle.read(_ID3_HEADER)
    if len(head) < _ID3_HEADER or not head.startswith(b"ID3"):
        return 0
    size = sum(
        (byte & 0x7F) << shift for byte, shift in zip(head[6:10], (21, 14, 7, 0), strict=True)
    )
    footer = _ID3_HEADER if head[5] & 0x10 else 0
    return _ID3_HEADER + size + footer


def _frame(header: bytes) -> tuple[int, int, int] | None:
    """(frame length, samples, sample rate) of a Layer III frame header, or None."""
    if (
        len(header) < _FRAME_HEADER
        or header[0] != _SYNC_BYTE
        or header[1] & _SYNC_BITS != _SYNC_BITS
    ):
        return None
    version = (header[1] >> 3) & _FIELD_MASK
    layer = (header[1] >> 1) & _FIELD_MASK
    bitrate_index = header[2] >> 4
    rate_index = (header[2] >> 2) & _FIELD_MASK
    if version == 1 or layer != _LAYER3 or bitrate_index in {0, 15} or rate_index == _RESERVED_RATE:
        return None
    table = _BITRATES[_MPEG1 if version == _MPEG1 else _MPEG2]
    rate = _SAMPLE_RATES[version][rate_index]
    samples = 1152 if version == _MPEG1 else 576
    length = samples // 8 * table[bitrate_index] * 1000 // rate + ((header[2] >> 1) & 1)
    return length, samples, rate


def scan_mp3_duration(handle: BinaryIO) -> float:
    """The exact duration of an MP3 from its frames, for a file with no Xing, VBRI or Info header.

    mutagen estimates such a file from the first frame's bitrate, which under-reads a VBR file by
    up to ten times; declaring that would leave the hold short of the billed duration.
    """
    handle.seek(_id3_size(handle))
    total = 0.0
    frames = 0
    skipped = 0
    while True:
        header = handle.read(_FRAME_HEADER)
        if len(header) < _FRAME_HEADER:
            break
        frame = _frame(header)
        if frame is None:
            skipped += 1
            if skipped > _RESYNC_LIMIT and frames == 0:
                break
            handle.seek(-(_FRAME_HEADER - 1), os.SEEK_CUR)
            continue
        length, samples, rate = frame
        total += samples / rate
        frames += 1
        handle.seek(length - _FRAME_HEADER, os.SEEK_CUR)
    if frames == 0:
        raise _unreadable("no MPEG frames")
    return total


class _Info(Protocol):
    length: float
    bitrate_mode: object


class _Parsed(Protocol):
    info: _Info


def _info(parser: Callable[[BinaryIO], object], handle: BinaryIO) -> _Info:
    """The stream info of a mutagen file; mutagen's own annotations leave it untyped."""
    return cast("_Parsed", parser(handle)).info


def _mp3(handle: BinaryIO) -> float:
    handle.seek(0)
    info = _info(MP3, handle)
    if info.bitrate_mode == BitrateMode.UNKNOWN:
        return scan_mp3_duration(handle)
    return float(info.length)


def _ogg(handle: BinaryIO) -> float:
    handle.seek(0)
    head = handle.read(512)
    handle.seek(0)
    marker = head.find(b"OpusHead")
    if marker < 0:
        return float(_info(OggVorbis, handle).length)
    # mutagen takes the pre-skip off the end; counting it keeps the declared value at or above
    # the container's own duration.
    (pre_skip,) = struct.unpack_from("<H", head, marker + _OPUS_PRE_SKIP_OFFSET)
    return float(_info(OggOpus, handle).length) + float(pre_skip) / _OPUS_RATE


def _read(kind: MediaFormat | None, handle: BinaryIO) -> float:
    handle.seek(0)
    if kind == "mp3":
        return _mp3(handle)
    if kind == "isobmff":
        return float(_info(MP4, handle).length)
    if kind == "wav":
        return float(_info(WAVE, handle).length)
    if kind == "flac":
        return float(_info(FLAC, handle).length)
    if kind == "ogg":
        return _ogg(handle)
    raise _unreadable("not a container the SDK reads")


def probe_duration(source: Source) -> float:
    """The file's duration in seconds (spec 8.2), read with mutagen.

    Raises UnsupportedMediaError (`duration_unreadable`) when it cannot be read; the caller then
    needs to pass the duration. The declared value is `ceil` of this, so the probe errs high.
    """
    kind = sniff(source.head())
    with source.probe_file() as handle:
        if handle is None:
            raise _unreadable("the input is a stream")
        try:
            seconds = _read(kind, handle)
        except (MutagenError, ValueError, struct.error, EOFError, OSError) as failure:
            raise _unreadable(type(failure).__name__) from failure
    if not math.isfinite(seconds) or seconds <= 0:
        raise _unreadable("the file reports no length")
    return seconds
