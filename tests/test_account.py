from __future__ import annotations

from datetime import UTC, datetime
from fractions import Fraction

import httpx
import pytest

from helpers import account_body, reply
from hushscript import Account, ApiError, Balance, UploadLimits
from hushscript.resources.account import minutes_of
from routes import async_hs_on, hs_on


@pytest.mark.parametrize(
    ("seconds", "minutes"),
    [(0, 0), (59, 0), (60, 1), (61, 1), (-1, 0), (-59, 0), (-60, -1), (-61, -1), (-90, -1)],
)
def test_minutes_truncate_toward_zero(seconds: int, minutes: int) -> None:
    assert minutes_of(seconds) == minutes
    assert str(minutes_of(seconds)) != "-0"


@pytest.mark.parametrize("seconds", [2**62 + 59, -(2**62) - 59, 10**18 + 7, -(10**18) - 7])
def test_minutes_are_exact_for_a_huge_balance(seconds: int) -> None:
    assert minutes_of(seconds) == int(Fraction(seconds, 60))


def test_balance_reads_the_account_net_of_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    body = account_body(
        balance_seconds=7260,
        held_seconds=30,
        credits_expire_at=1_798_859_045,
        purchases_remaining_in_window=2,
    )
    hs, routes = hs_on(monkeypatch, lambda _request: reply(200, body))
    balance = hs.balance()
    assert isinstance(balance, Balance)
    assert (balance.seconds, balance.minutes, balance.held_seconds) == (7260, 121, 30)
    assert balance.expires_at == datetime(2027, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert balance.purchases_remaining == 2
    assert routes.requests[0].url.path == "/v1/account"


def test_balance_without_the_optional_fields_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"balance_seconds": -59, "held_seconds": 0}
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    balance = hs.balance()
    assert (balance.seconds, balance.minutes) == (-59, 0)
    assert (balance.expires_at, balance.purchases_remaining) == (None, None)


def test_account_reads_every_field(monkeypatch: pytest.MonkeyPatch) -> None:
    body = account_body(card_on_file=False, data_region="us", purchases_remaining_in_window=1)
    body["x_new"] = {"anything": True}
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    account = hs.account()
    assert isinstance(account, Account)
    assert account == Account(
        balance_seconds=36000,
        held_seconds=0,
        credits_expire_at=None,
        card_on_file=False,
        data_region="us",
        limits=UploadLimits(
            max_daily_seconds=36000, max_active_jobs=50, active_jobs=0, used_today_seconds=0
        ),
        purchases_remaining_in_window=1,
    )


def _without(body: dict[str, object], key: str) -> dict[str, object]:
    return {k: v for k, v in body.items() if k != key}


BAD_BALANCES: list[object] = [
    [],
    "text",
    {"balance_seconds": "x", "held_seconds": 0},
    {"balance_seconds": 1},
    {"held_seconds": 1},
    {"balance_seconds": 1.5, "held_seconds": 0},
    {"balance_seconds": True, "held_seconds": 0},
    {"balance_seconds": 1, "held_seconds": -1},
    {"balance_seconds": 2**63, "held_seconds": 0},
    {"balance_seconds": 1, "held_seconds": 0, "credits_expire_at": "soon"},
    {"balance_seconds": 1, "held_seconds": 0, "credits_expire_at": 10**20},
    {"balance_seconds": 1, "held_seconds": 0, "credits_expire_at": -1},
    {"balance_seconds": 1, "held_seconds": 0, "purchases_remaining_in_window": "2"},
    {"balance_seconds": 1, "held_seconds": 0, "purchases_remaining_in_window": -1},
]


@pytest.mark.parametrize("body", BAD_BALANCES)
def test_balance_refuses_a_body_that_does_not_fit(
    monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    with pytest.raises(ApiError) as raised:
        hs.balance()
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        200,
        None,
    )
    assert "account response" in str(raised.value)


@pytest.mark.parametrize(
    "body",
    [
        _without(account_body(), "limits"),
        _without(account_body(), "card_on_file"),
        _without(account_body(), "data_region"),
        account_body(limits={"max_daily_seconds": 1}),
        account_body(limits={**account_body()["limits"], "active_jobs": -1}),  # type: ignore[dict-item]
        account_body(card_on_file="yes"),
        account_body(data_region=3),
    ],
)
def test_account_refuses_a_body_that_does_not_fit(
    monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    with pytest.raises(ApiError) as raised:
        hs.account()
    assert raised.value.code == "bad_response"


def test_balance_stays_lenient_about_the_account_only_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(
        monkeypatch, lambda _request: reply(200, {"balance_seconds": 5, "held_seconds": 1})
    )
    assert hs.balance().seconds == 5


@pytest.mark.anyio
async def test_the_async_client_reads_balance_and_account(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, account_body(balance_seconds=-61)))
    assert (await hs.balance()).minutes == -1
    assert (await hs.account()).balance_seconds == -61
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, []))
    with pytest.raises(ApiError) as balance_error:
        await hs.balance()
    assert (balance_error.value.code, balance_error.value.status) == ("bad_response", 200)
    with pytest.raises(ApiError) as account_error:
        await hs.account()
    assert (account_error.value.code, account_error.value.status) == ("bad_response", 200)


@pytest.mark.parametrize("content", [b"[" * 200_000, b"not json", b"\xff\xfe", b'{"a": NaN'])
def test_a_body_that_is_not_readable_json_is_a_bad_response(
    monkeypatch: pytest.MonkeyPatch, content: bytes
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _request: httpx.Response(200, content=content))
    with pytest.raises(ApiError) as raised:
        hs.balance()
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
