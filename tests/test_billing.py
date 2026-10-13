from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from conftest import TOKEN
from helpers import cancellation_notes, error_body, reply, snapshot
from hushscript import (
    ApiError,
    AsyncHushscript,
    AuthenticationError,
    ConflictError,
    Hushscript,
    HushscriptError,
    InsufficientBalanceError,
    NetworkError,
    NotFoundError,
    PaymentMethodRequiredError,
    PermissionDeniedError,
    PreflightError,
    Purchase,
    RateLimitError,
    ValidationError,
)
from routes import async_hs_on, hs_on

if TYPE_CHECKING:
    from routes import Handler

CARDS = "/v1/billing/cards"
PURCHASE = "/v1/billing/purchase"


def card(card_id: str, *, default: bool = False, eligible: bool = True) -> dict[str, object]:
    return {
        "id": card_id,
        "type": "card",
        "brand": "visa",
        "last4": "4242",
        "exp_month": 12,
        "exp_year": 2030,
        "email": None,
        "is_default": default,
        "fast_checkout_eligible": eligible,
    }


def cards_body(*methods: dict[str, object], default_id: str | None = None) -> dict[str, object]:
    return {"default_id": default_id, "methods": list(methods)}


class Shop:
    """A billing API: the cards it lists, then what each purchase answers."""

    def __init__(
        self,
        cards: dict[str, object] | None = None,
        purchases: list[httpx.Response | Exception] | None = None,
    ) -> None:
        self.cards = cards or cards_body(card("pm_1", default=True), default_id="pm_1")
        self.purchases = purchases or [reply(200, {"status": "ok", "balance_seconds": 18000})]
        self.log: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.log.append(snapshot(request))
        if request.url.path == CARDS:
            return reply(200, self.cards)
        assert request.url.path == PURCHASE, request.url.path
        step = self.purchases.pop(0) if len(self.purchases) > 1 else self.purchases[0]
        if isinstance(step, Exception):
            raise step
        return step

    def sent(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.log if r.url.path == PURCHASE]

    def paths(self) -> list[str]:
        return [r.url.path for r in self.log]


def buy(
    monkeypatch: pytest.MonkeyPatch, shop: Handler, pack: str = "300min", **kw: Any
) -> Purchase:
    hs, _ = hs_on(monkeypatch, shop)
    return hs.buy(pack, **kw)


def test_buy_reads_the_cards_buys_with_the_default_one_and_returns_the_answer_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop()
    purchase = buy(monkeypatch, shop)
    assert purchase == Purchase(seconds=18000, minutes=300)
    assert shop.paths() == [CARDS, PURCHASE]  # no follow-up read of the balance
    body = shop.sent()[0]
    assert set(body) == {"pack", "idempotency_key", "quick_payment_method_id", "policy_ack"}
    assert (body["pack"], body["quick_payment_method_id"]) == ("300min", "pm_1")
    assert uuid.UUID(body["idempotency_key"]).version == 4
    assert body["policy_ack"] is False


def test_the_notice_is_acknowledged_only_when_the_caller_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value, expected in ((True, True), (False, False), (1, False), ("yes", False)):
        shop = Shop()
        buy(monkeypatch, shop, acknowledge_no_refund=value)
        assert shop.sent()[0]["policy_ack"] is expected


def test_minutes_truncate_toward_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    for seconds, minutes in ((59, 0), (119, 1), (-61, -1)):
        shop = Shop(purchases=[reply(200, {"status": "ok", "balance_seconds": seconds})])
        assert buy(monkeypatch, shop) == Purchase(seconds, minutes)


def test_with_no_default_the_single_eligible_card_is_charged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(cards_body(card("pm_a", eligible=False), card("pm_b")))
    buy(monkeypatch, shop)
    assert shop.sent()[0]["quick_payment_method_id"] == "pm_b"


@pytest.mark.parametrize(
    ("methods", "code"),
    [
        ((), "no_default_card"),
        ((card("pm_a", eligible=False),), "no_default_card"),
        ((card("pm_a"), card("pm_b")), "default_card_required"),
    ],
)
@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_without_a_usable_card_nothing_is_sent(
    monkeypatch: pytest.MonkeyPatch,
    methods: tuple[dict[str, object], ...],
    code: str,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    shop = Shop(cards_body(*methods))
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    with pytest.raises(PaymentMethodRequiredError) as raised:
        await call_buy(hs)
    assert raised.value.code == code
    assert raised.value.status is None
    expected_hint = {
        "no_default_card": (
            "No saved card. Open the add-card link from the SDK's billing methods in a browser, "
            "or add a card in the app."
        ),
        "default_card_required": (
            "You have more than one saved card and none is the default. "
            "Set a default card with the SDK's billing methods or in the app."
        ),
    }
    assert raised.value.hint == expected_hint[code]
    assert raised.value.idempotency_key is None
    assert shop.paths() == [CARDS]


@pytest.mark.parametrize(
    "answer",
    [
        reply(200, {"status": "pending", "balance_seconds": 1}),
        reply(200, {"balance_seconds": 1}),
        reply(200, {"status": "ok"}),
        reply(200, {"status": "ok", "balance_seconds": 1.5}),
        reply(200, {"status": "ok", "balance_seconds": True}),
        reply(200, {"status": "ok", "balance_seconds": "5"}),
        reply(200, {"status": "ok", "balance_seconds": 2**70}),
        reply(200, ["ok"]),
        reply(200, None),
        httpx.Response(204),
        httpx.Response(200, content=b"[" * 5000),
    ],
)
def test_an_unusable_2xx_is_bad_response_that_carries_the_key(
    monkeypatch: pytest.MonkeyPatch, answer: httpx.Response
) -> None:
    shop = Shop(purchases=[answer])
    with pytest.raises(ApiError) as raised:
        buy(monkeypatch, shop)
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        answer.status_code,
        None,
    )
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    assert len(shop.sent()) == 1


def test_a_refusal_carries_the_key_and_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = reply(403, error_body("pat_purchase_requires_app", 4021))
    shop = Shop(purchases=[refusal])
    with pytest.raises(PermissionDeniedError) as raised:
        buy(monkeypatch, shop)
    assert raised.value.code == "pat_purchase_requires_app"
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    assert len(shop.sent()) == 1


@pytest.mark.parametrize(
    ("status", "error_class"),
    [(429, RateLimitError), (500, ApiError), (504, ApiError), (409, ConflictError)],
)
def test_other_statuses_are_not_retried_either(
    monkeypatch: pytest.MonkeyPatch, status: int, error_class: type[ApiError]
) -> None:
    shop = Shop(purchases=[reply(status, error_body("x", 1))])
    with pytest.raises(error_class) as raised:
        buy(monkeypatch, shop)
    assert type(raised.value) is error_class
    assert (raised.value.code, raised.value.status) == ("x", status)
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    assert len(shop.sent()) == 1


@pytest.mark.parametrize("status", [502, 503])
def test_a_502_or_503_is_retried_once_with_the_same_key(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    shop = Shop(purchases=[reply(status), reply(200, {"status": "ok", "balance_seconds": 600})])
    assert buy(monkeypatch, shop) == Purchase(600, 10)
    first, second = shop.sent()
    assert first == second


def test_at_most_one_retry_whatever_max_retries_says(monkeypatch: pytest.MonkeyPatch) -> None:
    shop = Shop(purchases=[reply(502)])
    with pytest.raises(ApiError) as raised:
        buy(monkeypatch, shop)
    assert raised.value.status == 502
    assert len(shop.sent()) == 2
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]


def test_a_network_error_is_retried_once_then_carries_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[httpx.ReadError("reset")])
    with pytest.raises(NetworkError) as raised:
        buy(monkeypatch, shop)
    assert len(shop.sent()) == 2
    assert shop.sent()[0] == shop.sent()[1]
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]


def test_a_purchase_that_provably_never_went_out_carries_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[httpx.ConnectError("refused")])
    with pytest.raises(NetworkError) as raised:
        buy(monkeypatch, shop)
    assert len(shop.sent()) == 2
    assert raised.value.idempotency_key is None
    assert raised.value.message == (
        "Could not reach the Hushscript API before the request was sent: "
        "POST /v1/billing/purchase (ConnectError: refused)."
    )


def test_a_purchase_that_may_have_gone_out_once_keeps_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[httpx.ReadError("reset"), httpx.ConnectError("refused")])
    with pytest.raises(NetworkError) as raised:
        buy(monkeypatch, shop)
    assert len(shop.sent()) == 2
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    assert raised.value.message == (
        "Could not reach the Hushscript API: POST /v1/billing/purchase (ConnectError: refused)."
    )


def test_a_key_from_a_failed_attempt_asks_again_with_the_same_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[reply(500), reply(200, {"status": "ok", "balance_seconds": 600})])
    with pytest.raises(HushscriptError) as raised:
        buy(monkeypatch, shop)
    key = raised.value.idempotency_key
    assert key
    assert buy(monkeypatch, shop, idempotency_key=key) == Purchase(600, 10)
    assert [body["idempotency_key"] for body in shop.sent()] == [key, key]


@pytest.mark.parametrize("key", ["", "a b", "a/b", "x" * 129, "ключ", "line\n", 5])
def test_a_key_that_breaks_the_purchase_rule_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch, key: object
) -> None:
    shop = Shop()
    with pytest.raises(PreflightError) as raised:
        buy(monkeypatch, shop, idempotency_key=key)
    assert raised.value.code == "invalid_option"
    assert shop.log == []


@pytest.mark.parametrize("pack", ["", None, 42, 300])
@pytest.mark.parametrize("resource", [False, True])
@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_a_pack_that_is_not_an_id_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
    pack: object,
    resource: bool,  # noqa: FBT001
    asynchronous: bool,  # noqa: FBT001
) -> None:
    shop = Shop()
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    with pytest.raises(PreflightError) as raised:
        await call_buy(hs, pack=cast("str", pack), resource=resource)
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert shop.log == []


def test_a_failure_reading_the_cards_has_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        return reply(401, error_body("unauthorized", 2000))

    hs, _ = hs_on(monkeypatch, broken)
    with pytest.raises(ApiError) as raised:
        hs.buy("300min")
    assert raised.value.idempotency_key is None


def test_the_billing_scope_error_names_both_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    shop = Shop(purchases=[reply(403, error_body("pat_scope_missing", 2023))])
    with pytest.raises(PermissionDeniedError) as raised:
        buy(monkeypatch, shop)
    assert raised.value.hint
    assert "Let this token buy minutes" in raised.value.hint
    assert "Let connected apps buy minutes" in raised.value.hint


def test_packs_cards_and_the_billing_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    pack = {
        "id": "300min",
        "amount": 599,
        "currency": "USD",
        "seconds": 18000,
        "referral_bonus_seconds": 600,
    }
    locked = {**pack, "id": "6000min", "available": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/billing/packs":
            return reply(200, {"packs": [pack, locked]})
        if request.url.path == CARDS:
            return reply(200, cards_body(card("pm_1", default=True), default_id="pm_1"))
        if request.url.path == "/v1/billing/cards/default":
            return reply(200, {"ok": True})
        return reply(
            200, {"checkout_url": "https://checkout.test/s", "session_id": "s", "expires_at": 1}
        )

    hs, routes = hs_on(monkeypatch, handler)
    packs = hs.billing.packs()
    assert [(p.id, p.minutes, p.price.formatted, p.bonus_minutes, p.available) for p in packs] == [
        ("300min", 300, "$5.99", 10, True),
        ("6000min", 300, "$5.99", 10, False),
    ]
    cards = hs.billing.cards()
    assert cards.default_id == "pm_1"
    assert cards.cards[0].fast_checkout_eligible
    hs.billing.set_default_card("pm_2")
    assert json.loads(routes.requests[-1].content) == {"payment_method_id": "pm_2"}
    assert hs.billing.add_card_url() == "https://checkout.test/s"
    assert "idempotency_key" in json.loads(routes.requests[-1].content)
    before = len(routes.requests)
    with pytest.raises(PreflightError) as raised:
        hs.billing.set_default_card("")
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert len(routes.requests) == before


def test_the_card_page_url_is_retried_once_after_a_502_with_the_same_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        reply(502),
        reply(200, {"checkout_url": "https://c.test/x", "session_id": "s", "expires_at": 1}),
    ]

    hs, routes = hs_on(monkeypatch, lambda _r: answers.pop(0))
    assert hs.billing.add_card_url() == "https://c.test/x"
    assert len(routes.requests) == 2
    assert len({r.content for r in routes.requests}) == 1
    assert uuid.UUID(json.loads(routes.requests[0].content)["idempotency_key"]).version == 4


@pytest.mark.parametrize(
    "body",
    [{}, {"checkout_url": ""}, {"checkout_url": 5}, []],
)
def test_an_unusable_setup_session_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, body))
    with pytest.raises(ApiError) as raised:
        hs.billing.add_card_url()
    assert raised.value.code == "bad_response"


def test_the_histories_walk_their_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        more = "c2" if cursor is None else None
        n = 1 if cursor is None else 2
        path = request.url.path
        if path.endswith("transactions"):
            return reply(
                200,
                {
                    "transactions": [
                        {
                            "id": n,
                            "seconds": 600,
                            "amount_cents": 599,
                            "amount_refunded_cents": 0,
                            "currency": "usd",
                            "status": "succeeded",
                            "created_at": 1_700_000_000,
                            "payment_method_type": None,
                            "payment_method_brand": "visa",
                            "payment_method_last4": "4242",
                            "receipt_number": None,
                            "initiated_via": "api",
                        }
                    ],
                    "next_cursor": more,
                    "account_reference": "x",
                },
            )
        if path.endswith("ledger"):
            entry = {
                "id": n,
                "delta_seconds": -5,
                "kind": "hold",
                "job_id": None,
                "note": None,
                "created_at": 1,
            }
            return reply(200, {"entries": [entry], "next_cursor": more})
        hold = {"id": f"h{n}", "kind": "transcription", "seconds": 5, "created_at": 1}
        return reply(200, {"holds": [hold], "next_cursor": more})

    hs, routes = hs_on(monkeypatch, handler)
    assert [t.id for t in hs.billing.transactions()] == [1, 2]
    assert [e.id for e in hs.billing.ledger()] == [1, 2]
    assert [h.id for h in hs.billing.holds()] == ["h1", "h2"]
    assert routes.queries()[:2] == [{}, {"cursor": "c2"}]
    first = next(hs.billing.transactions())
    assert (first.payment_method_brand, first.receipt_number, first.created_at.year) == (
        "visa",
        None,
        2023,
    )


@pytest.mark.parametrize("path", ["transactions", "ledger", "holds"])
def test_a_history_row_that_does_not_fit_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, {path: [{"id": 1}], "next_cursor": None}))
    with pytest.raises(ApiError) as raised:
        list(getattr(hs.billing, path)())
    assert raised.value.code == "bad_response"


# --- the asyncio client ---


@pytest.mark.anyio
async def test_the_async_buy_matches_the_sync_one(monkeypatch: pytest.MonkeyPatch) -> None:
    shop = Shop(purchases=[reply(502), reply(200, {"status": "ok", "balance_seconds": 600})])
    hs, _ = async_hs_on(monkeypatch, shop)
    assert await hs.buy("300min", acknowledge_no_refund=True) == Purchase(600, 10)
    first, second = shop.sent()
    assert first == second
    assert first["policy_ack"] is True


@pytest.mark.anyio
async def test_the_async_buy_carries_the_key_on_every_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[reply(200, {"status": "no"})])
    hs, _ = async_hs_on(monkeypatch, shop)
    with pytest.raises(ApiError) as raised:
        await hs.buy("300min")
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    empty = Shop(cards_body())
    hs, _ = async_hs_on(monkeypatch, empty)
    with pytest.raises(PaymentMethodRequiredError):
        await hs.buy("300min")
    assert empty.paths() == [CARDS]


@pytest.mark.anyio
async def test_a_cancel_after_the_purchase_was_sent_carries_the_key_as_a_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CARDS:
            return reply(200, cards_body(card("pm_1", default=True), default_id="pm_1"))
        raise asyncio.CancelledError

    hs, _ = async_hs_on(monkeypatch, handler)
    with pytest.raises(asyncio.CancelledError) as raised:
        await hs.buy("300min", idempotency_key="my-key")
    assert any("my-key" in note for note in cancellation_notes(raised.value))
    assert TOKEN  # the token is never in a note
    assert not any(TOKEN in note for note in cancellation_notes(raised.value))


@pytest.mark.anyio
async def test_the_async_billing_calls_and_histories(monkeypatch: pytest.MonkeyPatch) -> None:
    pack = {
        "id": "45min",
        "amount": 599,
        "currency": "USD",
        "seconds": 2700,
        "referral_bonus_seconds": 0,
    }

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: PLR0911  one answer per route
        path = request.url.path
        if path == "/v1/billing/packs":
            return reply(200, {"packs": [pack]})
        if path == CARDS:
            return reply(200, cards_body(card("pm_1", default=True), default_id="pm_1"))
        if path == "/v1/billing/cards/default":
            return reply(200, {"ok": True})
        if path == "/v1/billing/setup-session":
            return reply(200, {"checkout_url": "https://c.test/x"})
        if path.endswith("transactions"):
            return reply(200, {"transactions": [], "next_cursor": None})
        if path.endswith("ledger"):
            entry = {"id": 1, "delta_seconds": 5, "kind": "purchase", "created_at": 1}
            return reply(200, {"entries": [entry], "next_cursor": None})
        hold = {"id": "h1", "kind": "qa", "seconds": 5, "created_at": 1}
        return reply(200, {"holds": [hold], "next_cursor": None})

    hs, routes = async_hs_on(monkeypatch, handler)
    assert [p.id for p in await hs.billing.packs()] == ["45min"]
    assert (await hs.billing.cards()).default_id == "pm_1"
    await hs.billing.set_default_card("pm_1")
    assert await hs.billing.add_card_url() == "https://c.test/x"
    assert [t async for t in hs.billing.transactions()] == []
    assert [e.note async for e in hs.billing.ledger()] == [None]
    assert [h.kind async for h in hs.billing.holds()] == ["qa"]
    before = len(routes.requests)
    with pytest.raises(PreflightError) as raised:
        await hs.billing.set_default_card("")
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert len(routes.requests) == before


async def call_buy(
    hs: Hushscript | AsyncHushscript,
    pack: str = "300min",
    *,
    resource: bool = False,
    **kwargs: Any,
) -> Purchase:
    if isinstance(hs, AsyncHushscript):
        return await (hs.billing.buy if resource else hs.buy)(pack, **kwargs)
    return (hs.billing.buy if resource else hs.buy)(pack, **kwargs)


async def call_add_card_url(hs: Hushscript | AsyncHushscript) -> str:
    if isinstance(hs, AsyncHushscript):
        return await hs.billing.add_card_url()
    return hs.billing.add_card_url()


async def call_set_default_card(hs: Hushscript | AsyncHushscript, card_id: str) -> None:
    if isinstance(hs, AsyncHushscript):
        await hs.billing.set_default_card(card_id)
    else:
        hs.billing.set_default_card(card_id)


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("status", "slug", "number", "error_class"),
    [
        (400, "bad_request", 1000, ValidationError),
        (401, "unauthorized", 2000, AuthenticationError),
        (402, "insufficient_balance", 3001, InsufficientBalanceError),
        (403, "pat_purchase_requires_app", 4021, PermissionDeniedError),
        (403, "pat_purchase_requires_authentication", 4023, PermissionDeniedError),
        (404, "not_found", 4000, NotFoundError),
        (422, "unknown_pack", 1032, ValidationError),
    ],
)
async def test_purchase_refusals_keep_the_sent_key_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    status: int,
    slug: str,
    number: int,
    error_class: type[ApiError],
) -> None:
    shop = Shop(purchases=[reply(status, error_body(slug, number))])
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    with pytest.raises(error_class) as raised:
        await call_buy(hs)
    assert type(raised.value) is error_class
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        slug,
        status,
        number,
    )
    assert len(shop.sent()) == 1
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("pack", ["45min", "300min", "900min", "1800min", "6000min"])
@pytest.mark.parametrize("key", ["a", "x" * 128, "Az09_-"])
async def test_purchase_accepts_spec_pack_ids_and_key_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    pack: str,
    key: str,
) -> None:
    shop = Shop(purchases=[reply(201, {"status": "ok", "balance_seconds": 600})])
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    assert await call_buy(hs, pack, idempotency_key=key) == Purchase(600, 10)
    assert shop.paths() == [CARDS, PURCHASE]
    assert shop.sent()[0]["idempotency_key"] == key
    assert shop.sent()[0]["pack"] == pack


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_separate_purchases_mint_separate_uuid_keys(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    shop = Shop()
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    await call_buy(hs)
    await call_buy(hs)
    keys = [body["idempotency_key"] for body in shop.sent()]
    assert len(keys) == 2
    assert keys[0] != keys[1]
    assert all(uuid.UUID(key).version == 4 for key in keys)


def test_keyboard_interrupt_after_the_purchase_keeps_the_sent_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CARDS:
            return reply(200, cards_body(card("pm_1"), default_id="pm_1"))
        raise KeyboardInterrupt

    hs, routes = hs_on(monkeypatch, handler)
    with pytest.raises(KeyboardInterrupt) as raised:
        hs.buy("300min")
    [request] = [request for request in routes.requests if request.url.path == PURCHASE]
    key = json.loads(request.content)["idempotency_key"]
    assert getattr(raised.value, "__notes__", []) == [
        f"The purchase request was sent, so the card may have been charged. Idempotency key: {key}"
    ]
    assert TOKEN not in " ".join(getattr(raised.value, "__notes__", []))


@pytest.mark.anyio
async def test_cancel_during_the_cards_read_has_no_charge_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupted = asyncio.CancelledError()

    def handler(_request: httpx.Request) -> httpx.Response:
        raise interrupted

    hs, routes = async_hs_on(monkeypatch, handler)
    with pytest.raises(asyncio.CancelledError) as raised:
        await hs.buy("300min")
    assert raised.value is interrupted
    assert cancellation_notes(raised.value) == []
    assert [request.url.path for request in routes.requests] == [CARDS]


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure", [reply(502), reply(503), httpx.ReadError("reset")])
async def test_max_retries_zero_sends_a_purchase_once(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    failure: httpx.Response | Exception,
) -> None:
    shop = Shop(purchases=[failure])
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    client = (AsyncHushscript if asynchronous else Hushscript)(
        TOKEN, base_url="http://127.0.0.1:4010", max_retries=0
    )
    error_class = ApiError if isinstance(failure, httpx.Response) else NetworkError
    with pytest.raises(error_class) as raised:
        await call_buy(client)
    assert type(raised.value) is error_class
    assert (raised.value.code, raised.value.status) == (
        f"http_{failure.status_code}" if isinstance(failure, httpx.Response) else "network_error",
        failure.status_code if isinstance(failure, httpx.Response) else None,
    )
    assert len(shop.sent()) == 1
    assert raised.value.idempotency_key == shop.sent()[0]["idempotency_key"]
    if isinstance(hs, AsyncHushscript):
        await hs.aclose()
    else:
        hs.close()
    if isinstance(client, AsyncHushscript):
        await client.aclose()
    else:
        client.close()


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_setup_session_stops_after_two_502_answers(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    hs, routes = (async_hs_on if asynchronous else hs_on)(monkeypatch, lambda _r: reply(502))
    with pytest.raises(ApiError) as raised:
        await call_add_card_url(hs)
    assert (raised.value.code, raised.value.status) == ("http_502", 502)
    assert len(routes.requests) == 2
    assert routes.requests[0].content == routes.requests[1].content
    assert uuid.UUID(json.loads(routes.requests[0].content)["idempotency_key"]).version == 4


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("key", ["", "x" * 129, "a b", "a/b", "ключ", "line\n", 5])
async def test_both_clients_refuse_invalid_purchase_keys_without_requests(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    key: object,
) -> None:
    shop = Shop()
    hs, _ = (async_hs_on if asynchronous else hs_on)(monkeypatch, shop)
    with pytest.raises(PreflightError) as raised:
        await call_buy(hs, idempotency_key=key)
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert raised.value.idempotency_key is None
    assert shop.log == []


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("card_id", [".", "..", "\ud800", "", None, 42, 5])
async def test_both_clients_refuse_invalid_card_ids_without_requests(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    card_id: object,
) -> None:
    hs, routes = (async_hs_on if asynchronous else hs_on)(monkeypatch, lambda _r: reply(200, {}))
    with pytest.raises(PreflightError) as raised:
        await call_set_default_card(hs, cast("str", card_id))
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method", ["buy", "set_default_card"])
async def test_billing_ids_keep_their_original_text_in_request_bodies(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
    method: str,
) -> None:
    resource_id = "a/b?c#d é"

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == CARDS:
            return reply(200, cards_body(card("pm_1", default=True), default_id="pm_1"))
        return reply(200, {"status": "ok", "balance_seconds": 60})

    hs, routes = (async_hs_on if asynchronous else hs_on)(monkeypatch, answer)
    if method == "buy":
        await call_buy(hs, resource_id)
        field = "pack"
    else:
        await call_set_default_card(hs, resource_id)
        field = "payment_method_id"
    assert json.loads(routes.requests[-1].content)[field] == resource_id
