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
from helpers import (
    BASE_URL,
    FakeClock,
    Script,
    async_client,
    reply,
    settings_for,
    sync_client,
    transcript_body,
)
from hushscript import HushscriptError, OutcomeUnknownError, Purchase, Transcript
from hushscript._errors import parse_retry_after
from hushscript._http import AsyncRetryingTransport, RetryingTransport, _Attempt
from hushscript._redact import Credentials
from hushscript._response import parsed
from hushscript._shape import finite_number, number
from hushscript.transcribe.preflight import Media, Options, check_account, check_wait_timeout
from pipe import async_hs_for, hs_for, media
from routes import async_hs_on, hs_on
from test_billing import PURCHASE, Shop

SECRET_TEXT = f"stray failure with {TOKEN} in it"
SECRET_FORMS = f"stray {TOKEN.upper()} and {TOKEN.rpartition('.')[2]} in it"
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

CAP = float(2**53 - 1)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("7", 7.0),
        (" 12 ", 12.0),
        ("0" * 5000 + "7", 7.0),
        ("61", 61.0),
        (str(2**53 - 1), CAP),
        (str(2**53), CAP),
        ("9" * 400, CAP),
        ("9" * 5000, CAP),
        (str(2**63), CAP),
        (str(2**63 - 1), CAP),
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
    assert raised.value.retry_after == CAP
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


def written_then_failing(failure: Exception) -> httpx.MockTransport:
    """A transport that takes the whole request body, as a socket does, and then fails."""

    def handler(request: httpx.Request) -> httpx.Response:
        list(request.stream)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        raise failure

    return httpx.MockTransport(handler)


def async_written_then_failing(failure: Exception) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = [chunk async for chunk in request.stream]  # type: ignore[union-attr]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType, reportUnknownMemberType]
        raise failure

    return httpx.MockTransport(handler)


def test_a_stray_failure_on_a_claim_after_the_body_was_written_is_an_unknown_outcome() -> None:
    transport = RetryingTransport(
        written_then_failing(TypeError(SECRET_TEXT)), settings_for(FakeClock(), token=TOKEN)
    )
    with (
        httpx.Client(base_url=BASE_URL, transport=transport) as client,
        pytest.raises(OutcomeUnknownError) as raised,
    ):
        client.post("/v1/agent/accounts/sg_1/claim", json={})
    assert raised.value.code == "outcome_unknown"
    assert raised.value.hint
    assert TOKEN not in str(raised.value.__cause__)


@pytest.mark.anyio
async def test_async_a_stray_failure_on_a_rotation_after_the_send_is_an_unknown_outcome() -> None:
    transport = AsyncRetryingTransport(
        async_written_then_failing(TypeError(SECRET_TEXT)), settings_for(FakeClock(), token=TOKEN)
    )
    async with httpx.AsyncClient(base_url=BASE_URL, transport=transport) as client:
        with pytest.raises(OutcomeUnknownError):
            await client.post("/v1/agent/credentials/rotate", json={})


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


# --- R63: an SDK error from the caller's callback is the caller's too ---


def nested_failure() -> HushscriptError:
    """What a `buy()` inside a callback raises: an SDK error with its own key."""
    nested = HushscriptError("the nested buy failed", code="unexpected_error")
    nested.idempotency_key = "buy-key"
    return nested


@pytest.mark.parametrize("callback", ["on_resume_token", "on_progress"])
def test_an_sdk_error_from_a_callback_reaches_the_caller_with_its_own_key(
    monkeypatch: pytest.MonkeyPatch, callback: str
) -> None:
    mine = nested_failure()
    calls: list[object] = []

    def raiser(event: object) -> None:
        calls.append(event)
        if callback == "on_resume_token" or len(calls) > 1:  # the first progress is pre-send
            raise mine

    with pytest.raises(HushscriptError) as raised:
        hs_for(monkeypatch, FakeApi()).transcribe(
            media(),
            duration_seconds=100,
            idempotency_key="k" * 24,
            on_progress=raiser if callback == "on_progress" else None,
            on_resume_token=raiser if callback == "on_resume_token" else None,
        )
    assert raised.value is mine
    assert (mine.idempotency_key, mine.resume_token) == ("buy-key", None)


@pytest.mark.anyio
@pytest.mark.parametrize("callback", ["on_resume_token", "on_progress"])
async def test_async_an_sdk_error_from_a_callback_reaches_the_caller_with_its_own_key(
    monkeypatch: pytest.MonkeyPatch, callback: str
) -> None:
    mine = nested_failure()
    calls: list[object] = []

    def raiser(event: object) -> None:
        calls.append(event)
        if callback == "on_resume_token" or len(calls) > 1:
            raise mine

    with pytest.raises(HushscriptError) as raised:
        await async_hs_for(monkeypatch, FakeApi()).transcribe(
            media(),
            duration_seconds=100,
            idempotency_key="k" * 24,
            on_progress=raiser if callback == "on_progress" else None,
            on_resume_token=raiser if callback == "on_resume_token" else None,
        )
    assert raised.value is mine
    assert (mine.idempotency_key, mine.resume_token) == ("buy-key", None)


# --- the cause of an unexpected error is redacted with every form of the credentials ---


def check_forms_redacted(error: HushscriptError) -> None:
    text = str(error.__cause__)
    assert "TypeError" in text
    assert TOKEN.upper() not in text
    assert TOKEN.rpartition(".")[2] not in text


def explode_forms(*_args: object, **_kwargs: object) -> object:
    raise TypeError(SECRET_FORMS)


def test_the_cause_of_an_unexpected_purchase_error_is_redacted_with_the_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode_forms)
    hs, _ = hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        hs.buy("300min", idempotency_key="my-key")
    check_forms_redacted(raised.value)


@pytest.mark.anyio
async def test_async_the_cause_of_an_unexpected_purchase_error_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode_forms)
    hs, _ = async_hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        await hs.buy("300min", idempotency_key="my-key")
    check_forms_redacted(raised.value)


def whole_chain(error: BaseException) -> list[BaseException]:
    """The error and all that is reachable through `__cause__` and `__context__`."""
    seen: list[BaseException] = []
    pending: list[BaseException | None] = [error]
    while pending:
        current = pending.pop()
        if current is None or any(current is known for known in seen):
            continue
        seen.append(current)
        pending.extend([current.__cause__, current.__context__])
    return seen


def check_no_original_in_chain(error: HushscriptError) -> None:
    chain = whole_chain(error)
    assert error.__cause__ is not None
    assert error.__context__ is None
    assert not any(isinstance(link, TypeError) for link in chain)
    text = " ".join(f"{link} {link!r}" for link in chain)
    assert "TypeError" in text
    assert TOKEN not in text
    assert TOKEN.rpartition(".")[2] not in text


def test_an_unexpected_purchase_error_holds_no_unredacted_original_anywhere_in_its_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode)
    hs, _ = hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        hs.buy("300min", idempotency_key="my-key")
    assert raised.value.idempotency_key == "my-key"
    check_no_original_in_chain(raised.value)


@pytest.mark.anyio
async def test_async_an_unexpected_purchase_error_holds_no_unredacted_original_in_its_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing_module, "purchase_of", explode)
    hs, _ = async_hs_on(monkeypatch, Shop(purchases=[reply(200, OK)]))
    with pytest.raises(HushscriptError) as raised:
        await hs.buy("300min", idempotency_key="my-key")
    assert raised.value.idempotency_key == "my-key"
    check_no_original_in_chain(raised.value)


def test_the_cause_of_an_unexpected_pipeline_error_is_redacted_and_leaves_no_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "parse_created", explode_forms)
    with pytest.raises(HushscriptError) as raised:
        hs_for(monkeypatch, FakeApi()).transcribe(
            media(), duration_seconds=100, idempotency_key="k" * 24
        )
    check_forms_redacted(raised.value)
    assert raised.value.__context__ is None
    assert raised.value.idempotency_key == "k" * 24


@pytest.mark.anyio
async def test_async_the_cause_of_an_unexpected_pipeline_error_is_redacted_and_leaves_no_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode_async(*_args: object, **_kwargs: object) -> object:
        raise TypeError(SECRET_FORMS)

    monkeypatch.setattr(apipeline_module, "_upload", explode_async)
    tokens: list[str] = []
    with pytest.raises(HushscriptError) as raised:
        await async_hs_for(monkeypatch, FakeApi()).transcribe(
            media(), duration_seconds=100, idempotency_key="k" * 24, on_resume_token=tokens.append
        )
    check_forms_redacted(raised.value)
    assert raised.value.__context__ is None
    assert raised.value.resume_token == tokens[0]


# --- a failure before the request went out lost nothing ---


class UnreadingTransport(httpx.BaseTransport):
    """Fails without ever reading the request body, as a transport that breaks before the send."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise TypeError(f"{SECRET_TEXT} ({request.method})")


class AsyncUnreadingTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise TypeError(f"{SECRET_TEXT} ({request.method})")


class UnreadingAnswer(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Answers 200 without reading the body: the answer alone proves the request went out."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)


ROUTES = ["/v1/agent/accounts/sg_1/claim", "/v1/agent/credentials/rotate", "/v1/agent/accounts"]


@pytest.mark.parametrize("path", ROUTES)
def test_a_failure_before_a_claim_rotation_or_signup_was_sent_is_unexpected_not_unknown(
    path: str,
) -> None:
    transport = RetryingTransport(UnreadingTransport(), settings_for(FakeClock(), token=TOKEN))
    with (
        httpx.Client(base_url=BASE_URL, transport=transport) as client,
        pytest.raises(HushscriptError) as raised,
    ):
        client.post(path, json={})
    assert type(raised.value) is HushscriptError
    assert raised.value.code == "unexpected_error"
    assert TOKEN not in str(raised.value.__cause__)


@pytest.mark.anyio
@pytest.mark.parametrize("path", ROUTES)
async def test_async_a_failure_before_the_request_was_sent_is_unexpected_not_unknown(
    path: str,
) -> None:
    transport = AsyncRetryingTransport(
        AsyncUnreadingTransport(), settings_for(FakeClock(), token=TOKEN)
    )
    async with httpx.AsyncClient(base_url=BASE_URL, transport=transport) as client:
        with pytest.raises(HushscriptError) as raised:
            await client.post(path, json={})
    assert type(raised.value) is HushscriptError
    assert raised.value.code == "unexpected_error"


def test_a_failure_after_the_answer_came_is_unknown_even_when_the_body_was_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_attempt: _Attempt, _response: httpx.Response) -> object:
        raise TypeError(SECRET_TEXT)

    monkeypatch.setattr(_Attempt, "outcome_of", broken)
    transport = RetryingTransport(UnreadingAnswer(), settings_for(FakeClock(), token=TOKEN))
    with (
        httpx.Client(base_url=BASE_URL, transport=transport) as client,
        pytest.raises(OutcomeUnknownError),
    ):
        client.post("/v1/agent/credentials/rotate", json={})


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


# --- `annotated` surfaces what it swallowed without help from its caller ---


def sent_tracker() -> pipeline_module.Tracker:
    return pipeline_module.Tracker("k" * 24, "tok", sent=True, credentials=Credentials(TOKEN))


def test_annotated_raises_an_unexpected_failure_itself() -> None:
    def run() -> object:
        raise TypeError(SECRET_TEXT)

    with pytest.raises(HushscriptError) as raised:
        pipeline_module.annotated(sent_tracker(), run)
    assert (raised.value.idempotency_key, raised.value.resume_token) == ("k" * 24, "tok")
    check_no_original_in_chain(raised.value)


@pytest.mark.anyio
async def test_async_annotated_raises_an_unexpected_failure_itself() -> None:
    async def run() -> object:
        raise TypeError(SECRET_TEXT)

    with pytest.raises(HushscriptError) as raised:
        await apipeline_module.annotated(sent_tracker(), run)
    assert (raised.value.idempotency_key, raised.value.resume_token) == ("k" * 24, "tok")
    check_no_original_in_chain(raised.value)


def test_annotated_returns_what_the_block_returns_and_leaves_an_unsent_failure_alone() -> None:
    assert pipeline_module.annotated(sent_tracker(), lambda: 7) == 7
    unsent = pipeline_module.Tracker("k" * 24, credentials=Credentials(TOKEN))
    mine = TypeError("before the create")

    def run() -> object:
        raise mine

    with pytest.raises(TypeError) as raised:
        pipeline_module.annotated(unsent, run)
    assert raised.value is mine
