"""Prints the balance, the latest transcripts and the jobs still running.

python examples/balance.py
"""

from __future__ import annotations

import itertools
import sys

from hushscript import Hushscript, HushscriptError


def main() -> int:
    with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
        balance = hs.balance()
        # Held minutes are already taken out of `minutes`; do not subtract them again.
        print(f"{balance.minutes} minutes to spend, {balance.held_seconds} s held by running jobs")
        for transcript in itertools.islice(hs.transcripts.list(), 5):
            print(transcript.id, transcript.title)
        for job in hs.jobs.list(active=True):
            print("running", job.id, job.state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HushscriptError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        sys.exit(1)
