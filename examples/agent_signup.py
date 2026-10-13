"""Signs an agent account up, waits for the checkout to be paid, claims the token and rotates it.

The server shows each token once, so every one is written to the token file (mode 0600) the moment
it arrives, before anything else can fail.

    python examples/agent_signup.py --terms 2026-10-01 --token-file agent-token
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from hushscript import (
    AgentInfo,
    ConflictError,
    Hushscript,
    HushscriptError,
    OutcomeUnknownError,
)

POLL_SECONDS = 5


def looks_like_token(text: str | None) -> bool:
    """The shape the client checks of any token: the `hsr` prefix and printable ASCII only."""
    return text is not None and text.startswith("hsr") and all("!" <= char <= "~" for char in text)


def keep(path: Path, token: str) -> None:
    """Writes `token` to `path` with mode 0600. It goes to a private temporary file in the same
    directory first and replaces `path` by a rename, so the file never holds less than a whole token
    and an earlier token is never truncated before the new one is safely on disk."""
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".token-")  # created 0600
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(f"{token}\n")
            file.flush()
            os.fsync(file.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def run(terms: str, token_file: Path, kept: list[Path]) -> None:
    signup = Hushscript.agent_signup(
        email="agent@example.com",
        pack="45min",
        accept_terms=terms,
        agent=AgentInfo(name="Example agent", platform="custom"),
    )
    print(f"pay {signup.price.formatted} at {signup.checkout_url}")

    # The claim answers wrong_state until the checkout is paid. A lost answer is never retried.
    while True:
        try:
            account = Hushscript.agent_claim(signup.signup_id, signup.claim_secret)
            break
        except ConflictError as error:
            if error.code != "wrong_state":
                raise
            time.sleep(POLL_SECONDS)
    keep(token_file, account.token)  # before anything else can fail
    kept.append(token_file)
    print(f"claimed {account.user_id}; token saved to {token_file}")

    with Hushscript(account.token) as hs:
        print(f"{hs.balance().minutes} minutes")
        rotated = hs.agent.rotate_token()  # revokes the claimed token; the client sends the new one
        keep(token_file, rotated.token)
        kept.append(token_file)
        print(f"rotated; scopes: {', '.join(rotated.scopes)}; new token saved to {token_file}")


def main() -> int:
    arguments = argparse.ArgumentParser(description="Open an agent account and keep its token.")
    arguments.add_argument("--terms", required=True, help="the policy version you accept")
    arguments.add_argument("--token-file", required=True, type=Path, help="where tokens are kept")
    options = arguments.parse_args()
    kept: list[Path] = []
    try:
        run(options.terms, options.token_file, kept)
    except HushscriptError as error:
        print(f"{error.code}: {error.hint or error.message}", file=sys.stderr)
        received = error.received_token if isinstance(error, OutcomeUnknownError) else None
        received = (received or "").strip()
        if looks_like_token(received):
            keep(options.token_file, received)
            print(
                f"A token that came with the failed answer is in {options.token_file}.",
                file=sys.stderr,
            )
        elif kept:
            print(f"Any token that was issued is in {options.token_file}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
