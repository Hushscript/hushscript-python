"""Runs every program in examples/ against the conformance mock the container shares a network with.

Each example gets a fresh mock scenario, a sample recording and the arguments it documents. It runs
only through `just examples`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

# The mock accepts any hsr token.
MOCK_TOKEN = "hsr1:eu:pat." + "0" * 32 + "." + "0" * 64  # a made-up token for the mock
SCENARIO = {"mock": {"account": {"balance_seconds": 360000}, "completeState": "done"}}
TIMEOUT_SECONDS = 600
PRIVATE = 0o600


def base_url() -> str:
    return os.environ.get("HUSHSCRIPT_BASE_URL") or "http://127.0.0.1:4010"


def run() -> int:
    examples = sorted(Path("examples").glob("*.py"))
    if not examples:
        print("no examples found", file=sys.stderr)
        return 1
    failed = False
    with tempfile.TemporaryDirectory() as scratch, httpx.Client(base_url=base_url()) as mock:
        work = Path(scratch)
        media = mock.get("/__files/fixtures/media/cbr-20s.mp3").raise_for_status().content
        recordings = work / "recordings"
        recordings.mkdir()
        sample = work / "sample.mp3"
        for name in (sample, recordings / "one.mp3", recordings / "two.mp3"):
            name.write_bytes(media)
        token_file = work / "agent-token"
        # What each example is run with: the arguments it documents.
        arguments = {
            "balance": [],
            "transcribe": [str(sample)],
            "export_srt": [str(sample), str(work / "meeting.srt")],
            "batch_folder": [str(recordings), str(work / "transcripts")],
            "buy": ["300min", "--yes"],
            "agent_signup": ["--terms", "2026-10-01", "--token-file", str(token_file)],
        }
        environment = {
            **os.environ,
            "HUSHSCRIPT_BASE_URL": base_url(),
            "HUSHSCRIPT_TOKEN": MOCK_TOKEN,
        }
        for example in examples:
            mock.post("/__scenario", json=SCENARIO).raise_for_status()
            print("==", example.stem, flush=True)
            command = [sys.executable, str(example), *arguments.get(example.stem, [])]
            outcome = subprocess.run(  # our own interpreter and the files of this repository
                command, env=environment, check=False, timeout=TIMEOUT_SECONDS
            )
            if outcome.returncode != 0:
                print(f"FAILED {example.stem}: exit {outcome.returncode}")
                failed = True
        mode = token_file.stat().st_mode & 0o777 if token_file.exists() else None
        if mode != PRIVATE or token_file.stat().st_size == 0:
            print("FAILED agent_signup: the token file is missing, empty or not mode 0600")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
