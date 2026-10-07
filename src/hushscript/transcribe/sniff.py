from __future__ import annotations

from typing import Final, Literal

MediaFormat = Literal["mp3", "isobmff", "wav", "flac", "ogg"]

HEAD_BYTES: Final = 4096
_RIFF: Final = (b"RIFF", b"RF64", b"BW64")
_FRAME_SYNC_MASK: Final = 0xE0


def sniff(head: bytes) -> MediaFormat | None:
    """The container of `head` by its magic bytes (spec 8.1), never by the file name.

    Matches `backend/src/audio_probe.rs`: MP3 (an ID3 tag or a frame sync), ISO-BMFF (`ftyp` at
    offset 4: m4a, mp4, mov), WAV, FLAC and Ogg. Anything else is None.
    """
    if head.startswith(b"ID3") or (
        len(head) >= 2 and head[0] == 0xFF and head[1] & _FRAME_SYNC_MASK == _FRAME_SYNC_MASK  # noqa: PLR2004
    ):
        return "mp3"
    if len(head) >= 12 and head[4:8] == b"ftyp":  # noqa: PLR2004
        return "isobmff"
    if len(head) >= 12 and head[:4] in _RIFF and head[8:12] == b"WAVE":  # noqa: PLR2004
        return "wav"
    if head.startswith(b"fLaC"):
        return "flac"
    if head.startswith(b"OggS"):
        return "ogg"
    return None
