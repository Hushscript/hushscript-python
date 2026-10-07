"""Spends money: it needs a pack id and --yes before it charges the saved card.

python examples/buy.py 300min                 shows the packs and the notice, buys nothing
python examples/buy.py 300min --yes           buys the pack
python examples/buy.py 300min --yes --key KEY asks again with the key of an earlier attempt
"""

from __future__ import annotations

import argparse
import sys

from hushscript import Hushscript, HushscriptError

NOTICE = (
    "Minutes are added to your account instantly after payment. "
    "All purchases are final and non-refundable."
)
# The statuses of an answer that charged nothing: a refusal the body alone decides (400, 403 with
# 4021 or 4023, 404, 422) or a 402, which the API answers after its completed-purchase replay. A 401
# or a 429 is answered before that replay, so after the SDK's one retry it can follow a first
# attempt that charged. Any other outcome after the request was sent, a 401, a 408, a 409, a 429, a
# 5xx, no status at all or an unusable answer, may have reached the card.
REFUSALS = frozenset({400, 402, 403, 404, 422})


def may_have_charged(error: HushscriptError) -> bool:
    """True when the purchase request went out and the answer was not one of the refusals."""
    return error.idempotency_key is not None and error.status not in REFUSALS


def report(error: HushscriptError) -> None:
    print(f"{error.code}: {error.hint or error.message}", file=sys.stderr)
    if may_have_charged(error):
        print(
            "The card may have been charged. Run again with the same pack and "
            f"--key {error.idempotency_key}: it cannot charge twice.",
            file=sys.stderr,
        )
    else:
        print("Nothing was charged.", file=sys.stderr)


def parser() -> argparse.ArgumentParser:
    arguments = argparse.ArgumentParser(description="Buy a minute pack with the saved card.")
    arguments.add_argument("pack", help="the pack id to buy, one of the packs listed")
    arguments.add_argument("--yes", action="store_true", help="charge the saved card")
    arguments.add_argument("--key", help="the idempotency key an earlier attempt printed")
    return arguments


def main(pack: str, *, yes: bool, key: str | None) -> int:
    with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
        packs = hs.billing.packs()
        for candidate in packs:
            print(f"{candidate.id}: {candidate.minutes} minutes for {candidate.price.formatted}")
        chosen = next((candidate for candidate in packs if candidate.id == pack), None)
        if chosen is None:
            print("Name one of the packs above to buy it.", file=sys.stderr)
            return 2
        # Show the buyer this notice before the call; `acknowledge_no_refund` records it was shown.
        print(NOTICE)
        if not yes:
            print(
                f"Nothing was bought. Run again with --yes to charge your saved card "
                f"{chosen.price.formatted} for {chosen.id}."
            )
            return 1
        purchase = hs.buy(chosen.id, acknowledge_no_refund=True, idempotency_key=key)
        print(f"bought {chosen.id}; now {purchase.minutes} minutes")
    return 0


if __name__ == "__main__":
    options = parser().parse_args()
    try:
        sys.exit(main(options.pack, yes=options.yes, key=options.key))
    except HushscriptError as error:
        report(error)
        sys.exit(1)
