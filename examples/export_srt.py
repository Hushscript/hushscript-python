"""Transcribes one recording and writes it as subtitles.

python examples/export_srt.py meeting.mp3 meeting.srt
"""

from __future__ import annotations

import sys
from pathlib import Path

from hushscript import Hushscript, HushscriptError


def main(recording: str, out: str) -> int:
    with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
        transcript = hs.transcribe(recording)
    # Byte for byte what the Hushscript app exports; `captions=False` keeps one cue per utterance.
    Path(out).write_text(transcript.to_srt(), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: export_srt.py <recording> <subtitle file>", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    except HushscriptError as error:
        print(f"{error.code}: {error.hint or error.message}", file=sys.stderr)
        sys.exit(1)
