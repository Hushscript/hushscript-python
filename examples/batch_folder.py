"""Transcribes every recording in a folder, one after the other, and writes a text file for each.

python examples/batch_folder.py recordings transcripts
"""

from __future__ import annotations

import sys
from pathlib import Path

from hushscript import Hushscript, HushscriptError

AUDIO = {".mp3", ".m4a", ".mp4", ".mov", ".wav", ".flac", ".ogg", ".opus"}


def main(folder: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    failed = False
    with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
        for recording in sorted(folder.iterdir()):
            if not recording.is_file() or recording.suffix.lower() not in AUDIO:
                continue
            try:
                # Creates are paced for you (4 a minute), so a long folder just takes a while.
                transcript = hs.transcribe(recording)
            except HushscriptError as error:
                failed = True
                print(f"failed {recording.name}: {error.code} {error.hint or ''}".rstrip())
                continue
            (out / f"{recording.stem}.txt").write_text(transcript.text, encoding="utf-8")
            print("done", recording.name)
    return 1 if failed else 0


if __name__ == "__main__":
    arguments = sys.argv[1:] or ["recordings", "transcripts"]
    if len(arguments) != 2:
        print("usage: batch_folder.py <folder> <output folder>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(arguments[0]), Path(arguments[1])))
