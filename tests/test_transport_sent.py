from __future__ import annotations

import asyncio
from typing import cast

import httpx
import pytest

from helpers import (
    FakeClock,
    Script,
    SlowBody,
    async_client,
    error_body,
    failing_body,
    reply,
    settings_for,
    stand_in,
    sync_client,
)
from hushscript import NetworkError, OutcomeUnknownError
from hushscript._http import AsyncRetryingTransport

CLAIM = "/v1/agent/accounts/sg_1/claim"
ROTATE = "/v1/agent/credentials/rotate"
SIGNUP = "/v1/agent/accounts"
RATE_LIMITED = error_body("rate_limited", 5000)
RESET = httpx.ReadError("reset")


def _name(failure: Exception) -> str:
    return type(failure).__name__


# Spec 7.4: only these happen before the request body is written.
NOT_SENT = [httpx.ConnectError("x"), httpx.ConnectTimeout("x"), httpx.PoolTimeout("x")]
SENT = [
    httpx.ReadError("x"),
    httpx.ReadTimeout("x"),
    httpx.WriteError("x"),
    httpx.WriteTimeout("x"),
    httpx.RemoteProtocolError("x"),
    httpx.CloseError("x"),
]
UNRECOVERABLE = [
    (CLAIM, "The claim may have succeeded"),
    (ROTATE, "The old token may already be revoked"),
]


# --- a body that fails after the headers (verifier C1) ---


@pytest.mark.parametrize(("path", "hint"), UNRECOVERABLE)
def test_a_body_that_fails_after_the_headers_of_a_one_time_secret_is_unknown(
    path: str, hint: str
) -> None:
    script = Script([failing_body(httpx.ReadTimeout("slow"), chunks=(b'{"tok',))])
    with sync_client(script, FakeClock()) as client, pytest.raises(OutcomeUnknownError) as raised:
        client.post(path, json={})
    assert script.calls == 1
    assert raised.value.hint is not None
    assert hint in raised.value.hint
    assert stand_in(raised.value) == "ReadTimeout: slow"


def test_a_get_whose_body_fails_is_retried_and_then_a_network_error() -> None:
    script, clock = Script([failing_body(RESET)]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(NetworkError, match="Could not reach"):
        client.get("/v1/account")
    assert script.calls == 4
    assert len(clock.sleeps) == 3


def test_a_get_whose_body_fails_once_recovers() -> None:
    script = Script([failing_body(RESET), reply(200, {"ok": True})])
    with sync_client(script, FakeClock()) as client:
        assert client.get("/v1/account").json() == {"ok": True}
    assert script.calls == 2


def test_a_purchase_whose_body_fails_is_retried_once() -> None:
    script = Script([failing_body(RESET)])
    with sync_client(script, FakeClock(), max_retries=5) as client, pytest.raises(NetworkError):
        client.post("/v1/billing/purchase", json={})
    assert script.calls == 2


def test_another_mutation_whose_body_fails_is_not_retried() -> None:
    script = Script([failing_body(RESET)])
    with sync_client(script, FakeClock()) as client, pytest.raises(NetworkError):
        client.patch("/v1/org/members/u1", json={})
    assert script.calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize(("path", "hint"), UNRECOVERABLE)
async def test_async_a_failing_body_of_a_one_time_secret_is_unknown(path: str, hint: str) -> None:
    script = Script([failing_body(httpx.ReadTimeout("slow"))])
    async with async_client(script, FakeClock()) as client:
        with pytest.raises(OutcomeUnknownError) as raised:
            await client.post(path, json={})
    assert script.calls == 1
    assert raised.value.hint is not None
    assert hint in raised.value.hint


@pytest.mark.anyio
async def test_async_a_get_whose_body_fails_is_retried_and_then_a_network_error() -> None:
    script = Script([failing_body(RESET)])
    async with async_client(script, FakeClock()) as client:
        with pytest.raises(NetworkError):
            await client.get("/v1/account")
    assert script.calls == 4


@pytest.mark.anyio
async def test_async_a_purchase_whose_body_fails_is_retried_once() -> None:
    script = Script([failing_body(RESET)])
    async with async_client(script, FakeClock(), max_retries=5) as client:
        with pytest.raises(NetworkError):
            await client.post("/v1/billing/purchase", json={})
    assert script.calls == 2


# --- what counts as sent (spec 7.4, R16) ---


@pytest.mark.parametrize("failure", NOT_SENT, ids=_name)
def test_a_failure_before_the_body_is_written_is_a_plain_network_error(
    failure: httpx.TransportError,
) -> None:
    script = Script([failure])
    with sync_client(script, FakeClock()) as client, pytest.raises(NetworkError) as raised:
        client.post(CLAIM, json={})
    assert not isinstance(raised.value, OutcomeUnknownError)


@pytest.mark.parametrize("failure", SENT, ids=_name)
@pytest.mark.parametrize("path", [CLAIM, ROTATE, SIGNUP])
def test_any_other_failure_of_a_one_time_secret_route_counts_as_sent(
    path: str, failure: httpx.TransportError
) -> None:
    script = Script([failure])
    with sync_client(script, FakeClock()) as client, pytest.raises(OutcomeUnknownError):
        client.post(path, json={})
    assert script.calls == 1


@pytest.mark.parametrize("failure", NOT_SENT, ids=_name)
def test_a_mutation_is_retried_after_a_failure_before_the_body_was_written(
    failure: httpx.TransportError,
) -> None:
    script = Script([failure, reply(200, {})])
    with sync_client(script, FakeClock()) as client:
        assert client.patch("/v1/org/members/u1", json={}).status_code == 200
    assert script.calls == 2


@pytest.mark.parametrize("failure", SENT, ids=_name)
def test_a_mutation_is_not_retried_after_a_failure_that_may_have_sent_it(
    failure: httpx.TransportError,
) -> None:
    script = Script([failure, reply(200, {})])
    with sync_client(script, FakeClock()) as client, pytest.raises(NetworkError):
        client.delete("/v1/org/transcripts/t1/hold")
    assert script.calls == 1


# --- hints by exact route and the lost signup (verifier I1, R17) ---


def test_a_lost_signup_response_is_unknown_with_no_hint() -> None:
    script = Script([RESET])
    with sync_client(script, FakeClock()) as client, pytest.raises(OutcomeUnknownError) as raised:
        client.post(SIGNUP, json={})
    assert raised.value.hint is None
    assert raised.value.code == "outcome_unknown"
    assert stand_in(raised.value) == "ReadError: reset"
    assert script.calls == 1


@pytest.mark.parametrize(("path", "hint"), UNRECOVERABLE)
def test_each_unrecoverable_route_gets_its_own_hint(path: str, hint: str) -> None:
    script = Script([RESET])
    with sync_client(script, FakeClock()) as client, pytest.raises(OutcomeUnknownError) as raised:
        client.post(path, json={})
    assert raised.value.hint is not None
    assert raised.value.hint.startswith(hint)


def test_the_class_comes_from_the_path_relative_to_the_base_url() -> None:
    script = Script([RESET])
    with (
        sync_client(script, FakeClock(), base_url="http://127.0.0.1:4010/api") as client,
        pytest.raises(OutcomeUnknownError) as raised,
    ):
        client.post("/v1/agent/credentials/rotate", json={})
    assert raised.value.hint is not None
    assert raised.value.hint.startswith("The old token")
    assert script.requests[0].url.path == "/api/v1/agent/credentials/rotate"


# --- cancellation (R17): the CancelledError stays, the outcome rides along as a note ---


class _Hang(httpx.AsyncBaseTransport):
    """Reads the request body as the real transport does, then never answers."""

    def __init__(self, *, write_body: bool) -> None:
        self.write_body = write_body
        self.waiting = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.write_body:
            async for _ in cast("httpx.AsyncByteStream", request.stream):
                pass
        self.waiting.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


async def _cancel_after_connecting(path: str, *, write_body: bool) -> asyncio.CancelledError:
    inner = _Hang(write_body=write_body)
    transport = AsyncRetryingTransport(inner, settings_for(FakeClock()))
    async with httpx.AsyncClient(base_url="http://127.0.0.1:4010", transport=transport) as client:
        task = asyncio.ensure_future(client.post(path, json={}))
        await inner.waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as raised:
            await task
    assert task.cancelled()
    return raised.value


@pytest.mark.anyio
@pytest.mark.parametrize(("path", "hint"), UNRECOVERABLE)
async def test_cancelling_after_the_body_was_sent_leaves_the_outcome_in_a_note(
    path: str, hint: str
) -> None:
    cancelled = await _cancel_after_connecting(path, write_body=True)
    assert any(hint in note for note in cancelled.__notes__)


@pytest.mark.anyio
async def test_cancelling_a_signup_after_it_was_sent_notes_the_unknown_outcome() -> None:
    cancelled = await _cancel_after_connecting(SIGNUP, write_body=True)
    assert any("outcome is unknown" in note for note in cancelled.__notes__)


@pytest.mark.anyio
async def test_cancelling_before_the_body_was_written_adds_no_note() -> None:
    cancelled = await _cancel_after_connecting(CLAIM, write_body=False)
    assert not getattr(cancelled, "__notes__", [])


@pytest.mark.anyio
async def test_cancelling_a_call_with_a_harmless_route_adds_no_note() -> None:
    cancelled = await _cancel_after_connecting("/v1/billing/purchase", write_body=True)
    assert not getattr(cancelled, "__notes__", [])


# --- the overall per-request deadline (spec 3 and 7.1) ---


def _slow(clock: FakeClock, seconds: float, count: int) -> Script:
    def build() -> httpx.Response:
        return httpx.Response(200, stream=SlowBody(clock, seconds, count))

    return Script([build])


def test_a_response_that_trickles_past_the_deadline_times_out() -> None:
    clock = FakeClock()
    script = _slow(clock, 25.0, 5)
    with sync_client(script, clock, max_retries=0) as client, pytest.raises(NetworkError) as raised:
        client.get("/v1/account")
    assert "ReadTimeout" in str(raised.value)
    assert stand_in(raised.value) == "ReadTimeout: the request took longer than 60 s"


def test_a_get_past_the_deadline_is_retried() -> None:
    clock = FakeClock()
    script = _slow(clock, 25.0, 5)
    with sync_client(script, clock) as client, pytest.raises(NetworkError):
        client.get("/v1/account")
    assert script.calls == 4


def test_a_claim_past_the_deadline_is_unknown() -> None:
    clock = FakeClock()
    script = _slow(clock, 25.0, 5)
    with sync_client(script, clock) as client, pytest.raises(OutcomeUnknownError):
        client.post(CLAIM, json={})
    assert script.calls == 1


def test_a_response_inside_the_deadline_is_untouched() -> None:
    clock = FakeClock()
    script = _slow(clock, 25.0, 2)
    with sync_client(script, clock) as client:
        assert client.get("/v1/account").content == b"xx"


def test_the_deadline_restarts_on_every_attempt() -> None:
    clock = FakeClock()

    def slow() -> httpx.Response:
        return httpx.Response(200, stream=SlowBody(clock, 40.0, 1))

    script = Script([reply(503, headers={"Retry-After": "50"}), slow])
    with sync_client(script, clock) as client:
        assert client.get("/v1/account").status_code == 200
    assert script.calls == 2


def test_the_phase_timeouts_shrink_to_the_time_that_is_left() -> None:
    clock = FakeClock()
    script = _slow(clock, 40.0, 1)
    with sync_client(script, clock, max_retries=0) as client:
        client.get("/v1/account", timeout=httpx.Timeout(60.0, connect=5.0))
    first = script.requests[0].extensions["timeout"]
    assert first == {"connect": 5.0, "read": 20.0, "write": 20.0, "pool": 20.0}


@pytest.mark.anyio
async def test_async_a_response_that_trickles_past_the_deadline_times_out() -> None:
    clock = FakeClock()
    script = _slow(clock, 25.0, 5)
    async with async_client(script, clock) as client:
        with pytest.raises(NetworkError):
            await client.get("/v1/account")
    assert script.calls == 4
    claim = _slow(clock, 25.0, 5)
    async with async_client(claim, clock) as client:
        with pytest.raises(OutcomeUnknownError):
            await client.post(CLAIM, json={})
    assert claim.calls == 1
