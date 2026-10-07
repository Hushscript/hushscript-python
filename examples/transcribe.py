"""Transcribes one recording and prints the text.

python examples/transcribe.py meeting.mp3
"""

from __future__ import annotations

import sys

from hushscript import Hushscript, HushscriptError, Progress, UploadingProgress


def show(progress: Progress) -> None:
    if isinstance(progress, UploadingProgress):
        print(f"\ruploading {progress.percent}%", end="", flush=True)
    else:
        print(f"\r{progress.state}      ", end="", flush=True)


def main(path: str) -> int:
    with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
        transcript = hs.transcribe(path, on_progress=show)
    print()
    print(transcript.text)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: transcribe.py <recording>", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1]))
    except HushscriptError as error:
        print(f"{error.code}: {error.hint or error.message}", file=sys.stderr)
        if error.resume_token:
            print(
                f"Pick it up later with hs.resume({error.resume_token!r}, file).", file=sys.stderr
            )
        sys.exit(1)
