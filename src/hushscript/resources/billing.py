from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeVar, cast

from hushscript._errors import (
    HushscriptError,
    PaymentMethodRequiredError,
    raise_for_response,
    unexpected_error,
)
from hushscript._json import as_dict, as_list
from hushscript._response import BadBodyError, parsed
from hushscript._shape import (
    as_flag,
    as_text,
    as_whole,
    check_shape,
    maybe_text,
    to_datetime,
)
from hushscript._shapes import CARDS, HOLDS, LEDGER, PACKS, PURCHASE, SETUP_SESSION, TRANSACTIONS
from hushscript.money import Money, to_money
from hushscript.paginate import Page, apaginate, paginate
from hushscript.resources._params import list_params, path_id
from hushscript.resources.account import minutes_of
from hushscript.transcribe.preflight import invalid_option

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
    from datetime import datetime

    from hushscript._redact import Credentials
    from hushscript.transcribe.session import AsyncSession, SyncSession

PURCHASE_KEY: Final = re.compile(r"[A-Za-z0-9_-]{1,128}")
OK: Final = "ok"
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Pack:
    """A minute pack as the account can see it."""

    id: str
    """`45min`, `300min`, `900min`, `1800min` or `6000min`."""
    seconds: int
    minutes: int
    """`seconds / 60`, rounded toward zero."""
    price: Money
    """In the account's own currency, as the API states it: never hard-code one."""
    bonus_minutes: int
    """What an available referral bonus would add to this purchase; 0 when none."""
    available: bool
    """False only for an agent account's tier-locked pack."""


@dataclass(frozen=True, slots=True)
class Card:
    """A saved payment method."""

    id: str
    type: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    """`exp_month` and `exp_year` are 0 when the method has no expiry."""
    email: str | None
    is_default: bool
    fast_checkout_eligible: bool
    """Whether `buy()` may charge it without the buyer present."""


@dataclass(frozen=True, slots=True)
class Cards:
    """The saved payment methods and which one is the default."""

    default_id: str | None
    cards: list[Card]

    __hash__ = None  # type: ignore[assignment]  # holds a list, so it is unhashable by design


@dataclass(frozen=True, slots=True)
class Purchase:
    """What a purchase left the account with, read from the purchase answer alone."""

    seconds: int
    """The balance after the purchase settled: spendable now, holds already deducted."""
    minutes: int
    """`seconds / 60`, rounded toward zero."""


@dataclass(frozen=True, slots=True)
class Transaction:
    """One purchase, as the API reports it."""

    id: int
    seconds: int
    amount_cents: int
    amount_refunded_cents: int
    currency: str
    status: str
    created_at: datetime
    payment_method_type: str | None
    payment_method_brand: str | None
    payment_method_last4: str | None
    receipt_number: str | None
    """The public receipt reference, when there is one."""
    initiated_via: str | None


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One movement of the credit balance."""

    id: int
    delta_seconds: int
    kind: str
    job_id: str | None
    note: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Hold:
    """Seconds reserved by work still running; they are already deducted from the balance."""

    id: str
    kind: str
    """`transcription`, `translation`, `insights` or `qa`; a kind the SDK does not know yet passes
    through."""
    seconds: int
    created_at: datetime


def pack_list(body: object) -> list[Pack]:
    check_shape(body, PACKS, "pack list response")
    packs: list[Pack] = []
    for row in as_list((as_dict(body) or {})["packs"]) or []:
        item = as_dict(row) or {}
        seconds = as_whole(item["seconds"])
        packs.append(
            Pack(
                id=as_text(item["id"]),
                seconds=seconds,
                minutes=minutes_of(seconds),
                price=to_money(as_whole(item["amount"]), as_text(item["currency"])),
                bonus_minutes=minutes_of(as_whole(item["referral_bonus_seconds"])),
                available=item.get("available") is not False,
            )
        )
    return packs


def card_list(body: object) -> Cards:
    check_shape(body, CARDS, "card list response")
    fields = as_dict(body) or {}
    cards = [
        Card(
            id=as_text(item["id"]),
            type=as_text(item["type"]),
            brand=as_text(item["brand"]),
            last4=as_text(item["last4"]),
            exp_month=as_whole(item["exp_month"]),
            exp_year=as_whole(item["exp_year"]),
            email=maybe_text(item.get("email")),
            is_default=as_flag(item["is_default"]),
            fast_checkout_eligible=as_flag(item["fast_checkout_eligible"]),
        )
        for item in (as_dict(row) or {} for row in as_list(fields["methods"]) or [])
    ]
    return Cards(default_id=maybe_text(fields["default_id"]), cards=cards)


def purchase_of(body: object) -> Purchase:
    check_shape(body, PURCHASE, "purchase response")
    fields = as_dict(body) or {}
    if fields["status"] != OK:
        raise BadBodyError("purchase response (status: expected ok)")
    seconds = as_whole(fields["balance_seconds"])
    return Purchase(seconds=seconds, minutes=minutes_of(seconds))


def setup_url(body: object) -> str:
    check_shape(body, SETUP_SESSION, "setup session response")
    url = as_text((as_dict(body) or {})["checkout_url"])
    if not url:
        raise BadBodyError("setup session response (checkout_url: expected a URL)")
    return url


def transaction_page(body: object) -> Page[Transaction]:
    check_shape(body, TRANSACTIONS, "transaction list response")
    fields = as_dict(body) or {}
    items = [
        Transaction(
            id=as_whole(item["id"]),
            seconds=as_whole(item["seconds"]),
            amount_cents=as_whole(item["amount_cents"]),
            amount_refunded_cents=as_whole(item["amount_refunded_cents"]),
            currency=as_text(item["currency"]),
            status=as_text(item["status"]),
            created_at=to_datetime(item["created_at"]),
            payment_method_type=maybe_text(item.get("payment_method_type")),
            payment_method_brand=maybe_text(item.get("payment_method_brand")),
            payment_method_last4=maybe_text(item.get("payment_method_last4")),
            receipt_number=maybe_text(item.get("receipt_number")),
            initiated_via=maybe_text(item.get("initiated_via")),
        )
        for item in (as_dict(row) or {} for row in as_list(fields["transactions"]) or [])
    ]
    return Page(items=items, next_cursor=maybe_text(fields["next_cursor"]))


def ledger_page(body: object) -> Page[LedgerEntry]:
    check_shape(body, LEDGER, "ledger response")
    fields = as_dict(body) or {}
    items = [
        LedgerEntry(
            id=as_whole(item["id"]),
            delta_seconds=as_whole(item["delta_seconds"]),
            kind=as_text(item["kind"]),
            job_id=maybe_text(item.get("job_id")),
            note=maybe_text(item.get("note")),
            created_at=to_datetime(item["created_at"]),
        )
        for item in (as_dict(row) or {} for row in as_list(fields["entries"]) or [])
    ]
    return Page(items=items, next_cursor=maybe_text(fields["next_cursor"]))


def hold_page(body: object) -> Page[Hold]:
    check_shape(body, HOLDS, "hold list response")
    fields = as_dict(body) or {}
    items = [
        Hold(
            id=as_text(item["id"]),
            kind=as_text(item["kind"]),
            seconds=as_whole(item["seconds"]),
            created_at=to_datetime(item["created_at"]),
        )
        for item in (as_dict(row) or {} for row in as_list(fields["holds"]) or [])
    ]
    return Page(items=items, next_cursor=maybe_text(fields["next_cursor"]))


def purchase_key(idempotency_key: object) -> str:
    """The key a purchase goes out with: the caller's (1 to 128 of `A-Za-z0-9_-`, spec 7.3) or a
    fresh one."""
    if idempotency_key is None:
        return str(uuid.uuid4())
    if not isinstance(idempotency_key, str) or not PURCHASE_KEY.fullmatch(idempotency_key):
        raise invalid_option(
            "idempotency_key must be 1 to 128 characters from A-Z, a-z, 0-9, _ and -."
        )
    return idempotency_key


def check_pack(pack: object) -> str:
    if not isinstance(pack, str) or not pack:
        raise invalid_option("pack is a pack id such as 300min.")
    return pack


def choose_card(cards: Cards) -> str:
    """The card `buy()` charges: the default, else the only one that can be charged. With none
    usable it raises before anything is sent."""
    if cards.default_id:
        return cards.default_id
    eligible = [card.id for card in cards.cards if card.fast_checkout_eligible]
    if len(eligible) == 1:
        return eligible[0]
    if not eligible:
        raise PaymentMethodRequiredError(
            "The account has no saved card that can be charged.", code="no_default_card"
        )
    raise PaymentMethodRequiredError(
        "The account has no default card and several that can be charged.",
        code="default_card_required",
    )


def purchase_body(
    pack: str, key: str, card_id: str, *, acknowledge_no_refund: bool
) -> dict[str, object]:
    return {
        "pack": pack,
        "idempotency_key": key,
        "quick_payment_method_id": card_id,
        "policy_ack": acknowledge_no_refund is True,
    }


def _interrupted(interrupted: BaseException, key: str) -> None:
    interrupted.add_note(
        f"The purchase request was sent, so the card may have been charged. Idempotency key: {key}"
    )


def sent_purchase(key: str, credentials: Credentials, send: Callable[[], T]) -> T:
    """From the moment the purchase request goes out the card may have been charged, so every error
    carries the key (spec 6.5), whatever its kind; an interrupt is never converted, and carries it
    as a note. A failure of the SDK's own is raised once the handler has ended, so the unredacted
    original is on neither the cause nor the `__context__` of what the caller gets."""
    try:
        return send()
    except (asyncio.CancelledError, KeyboardInterrupt) as interrupted:
        _interrupted(interrupted, key)
        raise
    except HushscriptError as error:
        error.idempotency_key = key
        raise
    except Exception as failure:  # noqa: BLE001  # R61: nothing but an SDK error leaves
        failed = unexpected_error(failure, credentials)
    failed.idempotency_key = key
    raise failed


async def sent_purchase_async(
    key: str, credentials: Credentials, send: Callable[[], Awaitable[T]]
) -> T:
    """`sent_purchase` for the asyncio client."""
    try:
        return await send()
    except (asyncio.CancelledError, KeyboardInterrupt) as interrupted:
        _interrupted(interrupted, key)
        raise
    except HushscriptError as error:
        error.idempotency_key = key
        raise
    except Exception as failure:  # noqa: BLE001  # R61: nothing but an SDK error leaves
        failed = unexpected_error(failure, credentials)
    failed.idempotency_key = key
    raise failed


def check_card_id(card_id: object) -> str:
    path_id(card_id)
    return cast("str", card_id)


class Billing:
    """`hs.billing`: packs, cards, purchases and the billing history."""

    def __init__(self, session: SyncSession) -> None:
        self._session = session

    def packs(self) -> list[Pack]:
        """The minute packs the account can buy, priced in its own currency. Needs the billing
        scope."""
        return parsed(
            self._session.http.get("/v1/billing/packs"), self._session.credentials, pack_list
        )

    def cards(self) -> Cards:
        """The saved payment methods and the default one."""
        return parsed(
            self._session.http.get("/v1/billing/cards"), self._session.credentials, card_list
        )

    def set_default_card(self, card_id: str) -> None:
        """Makes a saved card the default one."""
        body = {"payment_method_id": check_card_id(card_id)}
        raise_for_response(
            self._session.http.post("/v1/billing/cards/default", json=body),
            credentials=self._session.credentials,
        )

    def add_card_url(self) -> str:
        """The hosted page where a card is saved: open it in a browser. The request carries a key,
        so its one retry after a 502 lands on the same page."""
        response = self._session.http.post(
            "/v1/billing/setup-session", json={"idempotency_key": str(uuid.uuid4())}
        )
        return parsed(response, self._session.credentials, setup_url)

    def buy(
        self,
        pack: str,
        *,
        acknowledge_no_refund: bool = False,
        idempotency_key: str | None = None,
    ) -> Purchase:
        """Buys a pack with the default card, or the only card that can be charged when there is no
        default, and returns the balance the purchase answer reports. It makes no request after the
        charge, so nothing can fail once the money has moved. Every error raised after the purchase
        request was sent carries `idempotency_key`; pass it back to ask again with no chance of a
        second charge. `acknowledge_no_refund` records that the no-refund notice was shown to the
        buyer; it is evidence for disputes and never gates the charge."""
        pack = check_pack(pack)
        key = purchase_key(idempotency_key)
        card_id = choose_card(self.cards())
        body = purchase_body(pack, key, card_id, acknowledge_no_refund=acknowledge_no_refund)

        def send() -> Purchase:
            response = self._session.http.post("/v1/billing/purchase", json=body)
            return parsed(response, self._session.credentials, purchase_of)

        return sent_purchase(key, self._session.credentials, send)

    def transactions(self) -> Iterator[Transaction]:
        """Every purchase, newest first, fetching pages as it goes."""
        return paginate(self._transactions)

    def ledger(self) -> Iterator[LedgerEntry]:
        """Every movement of the credit balance, newest first: holds, settles, releases, purchases
        and refunds."""
        return paginate(self._ledger)

    def holds(self) -> Iterator[Hold]:
        """The seconds reserved by work in flight, newest first."""
        return paginate(self._holds)

    def _transactions(self, cursor: str | None) -> Page[Transaction]:
        response = self._session.http.get(
            "/v1/billing/transactions", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, transaction_page)

    def _ledger(self, cursor: str | None) -> Page[LedgerEntry]:
        response = self._session.http.get("/v1/billing/ledger", params=list_params(cursor, None))
        return parsed(response, self._session.credentials, ledger_page)

    def _holds(self, cursor: str | None) -> Page[Hold]:
        response = self._session.http.get("/v1/billing/holds", params=list_params(cursor, None))
        return parsed(response, self._session.credentials, hold_page)


class AsyncBilling:
    """`hs.billing` on the asyncio client; the lists are async iterators."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def packs(self) -> list[Pack]:
        response = await self._session.http.get("/v1/billing/packs")
        return parsed(response, self._session.credentials, pack_list)

    async def cards(self) -> Cards:
        response = await self._session.http.get("/v1/billing/cards")
        return parsed(response, self._session.credentials, card_list)

    async def set_default_card(self, card_id: str) -> None:
        body = {"payment_method_id": check_card_id(card_id)}
        response = await self._session.http.post("/v1/billing/cards/default", json=body)
        raise_for_response(response, credentials=self._session.credentials)

    async def add_card_url(self) -> str:
        response = await self._session.http.post(
            "/v1/billing/setup-session", json={"idempotency_key": str(uuid.uuid4())}
        )
        return parsed(response, self._session.credentials, setup_url)

    async def buy(
        self,
        pack: str,
        *,
        acknowledge_no_refund: bool = False,
        idempotency_key: str | None = None,
    ) -> Purchase:
        pack = check_pack(pack)
        key = purchase_key(idempotency_key)
        card_id = choose_card(await self.cards())
        body = purchase_body(pack, key, card_id, acknowledge_no_refund=acknowledge_no_refund)

        async def send() -> Purchase:
            response = await self._session.http.post("/v1/billing/purchase", json=body)
            return parsed(response, self._session.credentials, purchase_of)

        return await sent_purchase_async(key, self._session.credentials, send)

    def transactions(self) -> AsyncIterator[Transaction]:
        return apaginate(self._transactions)

    def ledger(self) -> AsyncIterator[LedgerEntry]:
        return apaginate(self._ledger)

    def holds(self) -> AsyncIterator[Hold]:
        return apaginate(self._holds)

    async def _transactions(self, cursor: str | None) -> Page[Transaction]:
        response = await self._session.http.get(
            "/v1/billing/transactions", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, transaction_page)

    async def _ledger(self, cursor: str | None) -> Page[LedgerEntry]:
        response = await self._session.http.get(
            "/v1/billing/ledger", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, ledger_page)

    async def _holds(self, cursor: str | None) -> Page[Hold]:
        response = await self._session.http.get(
            "/v1/billing/holds", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, hold_page)
