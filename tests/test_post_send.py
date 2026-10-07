# pyright: reportPrivateUsage=false
"""R61 and R63: once a request is sent, every failure is an SDK error that carries the key or the
resume token, and every number the SDK parses is parsed totally. A callback's own error is the
caller's, and passes through unchanged."""

from __future__ import annotations

import contextlib
import json

import httpx
import pytest

import hushscript.resources.billing as billing_module
import hushscript.transcribe.apipeline as apipeline_module
import hushscript.transcribe.pipeline as pipeline_module
from conftest import TOKEN
from fakeapi import FakeApi
from helpers import FakeClock, Script, async_client, reply, sync_client, transcript_body
from hushscript import HushscriptError, OutcomeUnknownError, Purchase, Transcript
from hushscript._errors import parse_retry_after
from hushscript._http import _Attempt
from hushscript._redact import Credentials
from hushscript._response import parsed
from hushscript._shape import finite_number, number
from hushscript.transcribe.preflight import Media, Options, check_account, check_wait_timeout
from pipe import async_hs_for, hs_for, media
from routes import async_hs_on, hs_on
from test_billing import PURCHASE, Shop

SECRET_TEXT = f"stray failure with {TOKEN} in it"
OK = {"status": "ok", "balance_seconds": 600}


def explode(*_args: object, **_kwargs: object) -> object:
    raise TypeError(SECRET_TEXT)


def check_unexpected(error: HushscriptError) -> None:
    assert error.code == "unexpected_error"
    assert type(error) is HushscriptError
    cause = error.__cause__
    assert cause is not None
    assert "TypeError" in str(cause)
    assert TOKEN not in str(cause)
    assert TOKEN not in str(error)
    assert error.__suppress_context__


def raw(status: int, content: bytes, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status, content=content, headers={"content-type": "application/json", **(headers or {})}
    )


# --- total numbers ---


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("7", 7.0),
        (" 12 ", 12.0),
        ("0" * 5000 + "7", 7.0),
        ("9" * 400, None),
        ("9" * 5000, None),
        (str(2**63), None),
        (str(2**63 - 1), float(2**63 - 1)),
        ("1e400", None),
        ("NaN", None),
        ("Infinity", None),
        ("-1", None),
        ("١٢", None),
        ("", None),
    ],
    ids=lambda value: str(value)[:12],
)
def test_a_retry_after_is_read_totally(header: str, expected: float | None) -> None:
    assert parse_retry_after(header) == expected


def test_a_purchase_answered_200_with_a_huge_retry_after_still_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[reply(200, OK, headers={"Retry-After": "9" * 400})])
    hs, _ = hs_on(monkeypatch, shop)
    assert hs.buy("300min") == Purchase(600, 10)


@pytest.mark.parametrize("status", [402, 429])
@pytest.mark.parametrize(
    "details",
    [
        b'"needed_seconds":1e400,"balance_seconds":NaN',
        b'"retry_after_seconds":Infinity,"used_seconds":-Infinity',
        b'"needed_seconds":1' + b"0" * 400 + b',"max_seconds":-1' + b"0" * 400,
    ],
    ids=["1e400-and-nan", "infinities", "400-digits"],
)
def test_a_refused_purchase_with_unusable_numbers_is_an_sdk_error_with_the_key(
    monkeypatch: pytest.MonkeyPatch, status: int, details: bytes
) -> None:
    slug = b"insufficient_balance" if status == 402 else b"rate_limited"
    body = b'{"error":"' + slug + b'","code":1,' + details + b"}"
    shop = Shop(purchases=[raw(status, body, {"Retry-After": "9" * 400})])
    hs, _ = hs_on(monkeypatch, shop)
    with pytest.raises(HushscriptError) as raised:
        hs.buy("300min", idempotency_key="my-key")
    assert raised.value.status == status
    assert raised.value.idempotency_key == "my-key"
    assert raised.value.retry_after is None
    assert "inf" not in (raised.value.hint or "").lower()
    assert "nan" not in (raised.value.hint or "").lower()


@pytest.mark.parametrize(
    "balance",
    [-(10**400), 10**400, float("inf"), 2**63, -(2**63)],
    ids=["-400-digits", "400-digits", "inf", "2**63", "-2**63"],
)
def test_the_preflight_balance_read_never_overflows(balance: float) -> None:
    account = {
        "balance_seconds": balance,
        "limits": {"max_daily_seconds": balance, "used_today_seconds": 10**400},
    }
    with contextlib.suppress(HushscriptError):
        check_account(account, Media(size=1000, duration_seconds=60), Options())


# --- a stray failure after the send ---


def test_a_stray_failure_after_the_purchase_was_sent_carries_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode)
    hs, _ = hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        hs.buy("300min", idempotency_key="my-key")
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "my-key"


@pytest.mark.anyio
async def test_async_a_stray_failure_after_the_purchase_was_sent_carries_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode)
    hs, _ = async_hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        await hs.buy("300min", idempotency_key="my-key")
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "my-key"


def test_a_stray_failure_in_the_transport_is_an_sdk_error_and_the_purchase_keeps_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Shop(purchases=[reply(200, OK)])
    hs, _ = hs_on(monkeypatch, shop)
    real = _Attempt.outcome_of

    def outcome_of(attempt: _Attempt, response: httpx.Response) -> object:
        if attempt.request.url.path == PURCHASE:
            raise TypeError(SECRET_TEXT)
        return real(attempt, response)

    monkeypatch.setattr(_Attempt, "outcome_of", outcome_of)
    with pytest.raises(HushscriptError) as raised:
        hs.buy("300min", idempotency_key="my-key")
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "my-key"
    assert len(shop.sent()) == 1


@pytest.mark.parametrize("failure", [TypeError(SECRET_TEXT), OverflowError(SECRET_TEXT)])
def test_a_stray_failure_inside_the_transport_never_escapes_raw(failure: Exception) -> None:
    client = sync_client(Script([failure]), FakeClock())
    with pytest.raises(HushscriptError) as raised:
        client.get("/v1/account")
    assert raised.value.code == "unexpected_error"
    assert TOKEN not in str(raised.value.__cause__)


@pytest.mark.anyio
async def test_async_a_stray_failure_inside_the_transport_never_escapes_raw() -> None:
    client = async_client(Script([TypeError(SECRET_TEXT)]), FakeClock())
    with pytest.raises(HushscriptError) as raised:
        await client.get("/v1/account")
    assert raised.value.code == "unexpected_error"


def test_a_stray_failure_on_a_claim_is_an_unknown_outcome() -> None:
    client = sync_client(Script([TypeError(SECRET_TEXT)]), FakeClock())
    with pytest.raises(OutcomeUnknownError) as raised:
        client.post("/v1/agent/accounts/sg_1/claim", json={})
    assert raised.value.code == "outcome_unknown"
    assert raised.value.hint
    assert TOKEN not in str(raised.value.__cause__)


@pytest.mark.anyio
async def test_async_a_stray_failure_on_a_rotation_is_an_unknown_outcome() -> None:
    client = async_client(Script([TypeError(SECRET_TEXT)]), FakeClock())
    with pytest.raises(OutcomeUnknownError):
        await client.post("/v1/agent/credentials/rotate")


def test_a_stray_failure_after_the_create_carries_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_module, "parse_created", explode)
    hs = hs_for(monkeypatch, FakeApi())
    with pytest.raises(HushscriptError) as raised:
        hs.transcribe(media(), duration_seconds=100, idempotency_key="k" * 24)
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "k" * 24
    assert raised.value.resume_token is None


def test_a_stray_failure_after_the_token_carries_the_key_and_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "_upload", explode)
    hs = hs_for(monkeypatch, FakeApi())
    tokens: list[str] = []
    with pytest.raises(HushscriptError) as raised:
        hs.transcribe(
            media(), duration_seconds=100, idempotency_key="k" * 24, on_resume_token=tokens.append
        )
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "k" * 24
    assert raised.value.resume_token == tokens[0]


@pytest.mark.anyio
async def test_async_a_stray_failure_after_the_token_carries_the_key_and_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode_async(*_args: object, **_kwargs: object) -> object:
        raise TypeError(SECRET_TEXT)

    monkeypatch.setattr(apipeline_module, "_upload", explode_async)
    api = FakeApi()
    ahs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(HushscriptError) as raised:
        await ahs.transcribe(
            media(), duration_seconds=100, idempotency_key="k" * 24, on_resume_token=tokens.append
        )
    check_unexpected(raised.value)
    assert raised.value.idempotency_key == "k" * 24
    assert raised.value.resume_token == tokens[0]


# --- the caller's own callbacks ---


class MineError(Exception):
    pass


def test_an_error_from_on_resume_token_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs = hs_for(monkeypatch, FakeApi())
    mine = MineError("mine")

    def callback(_token: str) -> None:
        raise mine

    with pytest.raises(MineError) as raised:
        hs.transcribe(media(), duration_seconds=100, on_resume_token=callback)
    assert raised.value is mine


def test_an_error_from_on_progress_after_the_send_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs = hs_for(monkeypatch, FakeApi())
    mine = MineError("mine")
    calls: list[object] = []

    def callback(progress: object) -> None:
        calls.append(progress)
        if len(calls) > 1:  # the first event is before the create
            raise mine

    with pytest.raises(MineError) as raised:
        hs.transcribe(media(), duration_seconds=100, on_progress=callback)
    assert raised.value is mine


@pytest.mark.anyio
async def test_async_an_error_from_a_callback_after_the_send_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine = MineError("mine")

    def on_token(_token: str) -> None:
        raise mine

    with pytest.raises(MineError) as raised:
        await async_hs_for(monkeypatch, FakeApi()).transcribe(
            media(), duration_seconds=100, on_resume_token=on_token
        )
    assert raised.value is mine
    calls: list[object] = []

    def on_progress(progress: object) -> None:
        calls.append(progress)
        if len(calls) > 1:
            raise mine

    with pytest.raises(MineError) as raised:
        await async_hs_for(monkeypatch, FakeApi()).transcribe(
            media(), duration_seconds=100, on_progress=on_progress
        )
    assert raised.value is mine


@pytest.mark.parametrize("wait_timeout", [10**400, -(10**400)])
def test_an_option_that_is_a_huge_int_is_judged_not_overflowed(wait_timeout: int) -> None:
    if wait_timeout > 0:
        check_wait_timeout(wait_timeout)
    else:
        with pytest.raises(HushscriptError):
            check_wait_timeout(wait_timeout)


@pytest.mark.parametrize("value", [10**400, -(10**400), float("nan"), float("inf"), 2**63])
def test_a_number_field_that_is_out_of_range_is_a_problem_not_an_overflow(value: float) -> None:
    assert number(value) is not None
    assert not finite_number(value)


def test_a_huge_int_in_a_timestamp_of_a_transcript_is_a_bad_response() -> None:
    body = transcript_body(
        body={
            "version": 1,
            "original": {
                "utterances": [{"speaker": "A", "start_ms": 10**400, "end_ms": 5, "text": "x"}]
            },
            "translations": {},
        }
    )
    response = httpx.Response(200, content=json.dumps(body).encode())
    with pytest.raises(HushscriptError) as raised:
        parsed(response, Credentials(TOKEN), Transcript.from_api)
    assert raised.value.code == "bad_response"
