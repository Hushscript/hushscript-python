# pyright: reportPrivateUsage=false
"""Transport behavior the transcribe pipeline relies on (Task 10 review carry-overs, spec 7.2)."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import httpx
import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import (
    BASE_URL,
    FakeClock,
    Script,
    SlowBody,
    async_client,
    error_body,
    failing_body,
    reply,
    settings_for,
    sync_client,
)
from hushscript import (
    AsyncHushscript,
    Hushscript,
    NetworkError,
    OutcomeUnknownError,
)
from hushscript._clock import SystemClock
from hushscript._errors import ApiError
from hushscript._http import (
    CLASS_EXTENSION,
    STREAM_EXTENSION,
    AsyncRetryingTransport,
)
from hushscript._pacing import TokenBucket
from hushscript._retry import RetryClass

if TYPE_CHECKING:
    from collections.abc import Iterator

CLAIM = "/v1/agent/accounts/sg_1/claim"
CREATE = "/v1/uploads"
PART = "/v1/uploads/job_1/parts/1"
KEYED = {"size_bytes": 5, "duration_seconds": 20, "idempotency_key": "k" * 20}


# --- a body that cannot be decoded is a body failure like any other ---


def test_a_get_whose_body_cannot_be_decoded_is_retried_then_a_network_error() -> None:
    script = Script([failing_body(httpx.DecodingError("bad gzip"))])
    with sync_client(script, FakeClock()) as client, pytest.raises(NetworkError) as raised:
        client.get("/v1/account")
    assert script.calls == 4
    assert isinstance(raised.value.__cause__, httpx.DecodingError)


def test_a_claim_whose_body_cannot_be_decoded_is_unknown() -> None:
    script = Script([failing_body(httpx.DecodingError("bad gzip"))])
    with sync_client(script, FakeClock()) as client, pytest.raises(OutcomeUnknownError):
        client.post(CLAIM, json={})
    assert script.calls == 1


def test_a_real_gzip_body_that_is_broken_is_a_decoding_failure() -> None:
    script = Script(
        [
            lambda: httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(b"not gzip")
            )
        ]
    )
    with sync_client(script, FakeClock(), max_retries=0) as client, pytest.raises(NetworkError):
        client.get("/v1/account")


@pytest.mark.anyio
async def test_async_a_body_that_cannot_be_decoded_is_a_failure() -> None:
    script = Script([failing_body(httpx.DecodingError("bad gzip"))])
    async with async_client(script, FakeClock()) as client:
        with pytest.raises(NetworkError):
            await client.get("/v1/account")
        with pytest.raises(OutcomeUnknownError):
            await client.post(CLAIM, json={})
    assert script.calls == 5


# --- the deadline follows the request's own timeout, up to a ceiling ---


def _slow(clock: FakeClock, seconds: float, count: int) -> Script:
    def build() -> httpx.Response:
        return httpx.Response(200, stream=SlowBody(clock, seconds, count))

    return Script([build])


def test_a_response_held_240_seconds_succeeds_at_300_and_fails_at_the_default() -> None:
    clock = FakeClock()
    with sync_client(_slow(clock, 240.0, 1), clock, max_retries=0) as client:
        assert client.get("/v1/account", timeout=httpx.Timeout(300.0)).content == b"x"
    clock = FakeClock()
    with (
        sync_client(_slow(clock, 240.0, 1), clock, max_retries=0) as client,
        pytest.raises(NetworkError),
    ):
        client.get("/v1/account")


def test_a_timeout_above_the_ceiling_is_held_to_the_ceiling() -> None:
    clock = FakeClock()
    settings = settings_for(clock)
    assert settings.ceiling == 300.0
    with (
        sync_client(_slow(clock, 200.0, 2), clock, max_retries=0) as client,
        pytest.raises(NetworkError),
    ):
        client.get("/v1/account", timeout=httpx.Timeout(3600.0))


def test_a_configured_timeout_above_300_raises_the_ceiling_with_it() -> None:
    assert settings_for(FakeClock(), timeout=900.0).ceiling == 900.0


def test_the_api_client_with_a_longer_timeout_really_waits_longer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    script = _slow(clock, 80.0, 2)
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    hs = Hushscript(TOKEN, base_url=BASE_URL, clock=clock, max_retries=0)
    derived = hs.api.with_timeout(httpx.Timeout(300.0))
    assert derived.get_httpx_client().get("/v1/account").status_code == 200
    with pytest.raises(NetworkError):
        hs.api.get_httpx_client().get("/v1/account")


class _Hangs(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
        await asyncio.sleep(30)
        return httpx.Response(200)


@pytest.mark.anyio
async def test_async_a_request_blocked_on_the_network_is_cut_at_its_deadline() -> None:
    transport = AsyncRetryingTransport(
        _Hangs(), settings_for(FakeClock(), max_retries=1, timeout=0.05)
    )
    async with httpx.AsyncClient(base_url="http://127.0.0.1:4010", transport=transport) as client:
        with pytest.raises(NetworkError) as raised:
            await client.get("/v1/account")
    assert isinstance(raised.value.__cause__, httpx.ReadTimeout)


@pytest.mark.anyio
async def test_async_a_caller_timeout_is_not_taken_for_ours() -> None:
    transport = AsyncRetryingTransport(_Hangs(), settings_for(FakeClock()))
    async with httpx.AsyncClient(base_url="http://127.0.0.1:4010", transport=transport) as client:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await client.get("/v1/account")


# --- a part's response body is left unread ---


class _Counting(httpx.SyncByteStream):
    def __init__(self) -> None:
        self.read = 0

    def __iter__(self) -> Iterator[bytes]:
        for _ in range(3):
            self.read += 1
            yield b"x"


def _counted() -> tuple[_Counting, Script]:
    body = _Counting()
    return body, Script([lambda: httpx.Response(200, stream=body)])


def test_a_stream_flagged_response_is_not_buffered_by_the_transport() -> None:
    body, script = _counted()
    with sync_client(script, FakeClock()) as client:
        request = client.build_request(
            "PUT", PART, content=b"data", extensions={STREAM_EXTENSION: True}
        )
        response = client.send(request, stream=True)
        assert body.read == 0
        assert b"".join(response.iter_bytes()) == b"xxx"
        response.close()


def test_without_the_flag_the_transport_reads_the_whole_body() -> None:
    body, script = _counted()
    with sync_client(script, FakeClock()) as client:
        client.put(PART, content=b"data")
    assert body.read == 3


def test_a_route_that_needs_the_body_ignores_the_flag() -> None:
    script = Script(
        [reply(429, error_body("too_many_active_jobs", 5001)), reply(200, {"ok": True})]
    )
    with sync_client(script, FakeClock()) as client:
        request = client.build_request(
            "POST", CREATE, json=KEYED, extensions={STREAM_EXTENSION: True}
        )
        response = client.send(request, stream=True)
        response.read()
    assert script.calls == 2


@pytest.mark.anyio
async def test_async_a_stream_flagged_response_is_not_buffered() -> None:
    script = Script([lambda: httpx.Response(200, stream=httpx.ByteStream(b"{}"))])
    async with async_client(script, FakeClock()) as client:
        request = client.build_request(
            "PUT", PART, content=b"data", extensions={STREAM_EXTENSION: True}
        )
        response = await client.send(request, stream=True)
        assert not response.is_stream_consumed
        await response.aread()
        await response.aclose()


# --- a create is retried only with a key (spec 7.2) ---


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_keyed_create_is_retried(status: int) -> None:
    script = Script(
        [reply(status, error_body("rate_limited", 5000))] * 2 + [reply(200, {"job_id": "j"})]
    )
    with sync_client(script, FakeClock()) as client:
        assert client.post(CREATE, json=KEYED).status_code == 200
    assert script.calls == 3


@pytest.mark.parametrize(
    "body",
    [
        {"size_bytes": 5, "duration_seconds": 20},
        {**KEYED, "idempotency_key": ""},
        {**KEYED, "idempotency_key": None},
        {**KEYED, "idempotency_key": 7},
    ],
)
def test_a_create_without_a_usable_key_is_not_retried_on_a_status(body: dict[str, object]) -> None:
    script = Script([reply(503, error_body("server_error", 9000))])
    with sync_client(script, FakeClock()) as client:
        assert client.post(CREATE, json=body).status_code == 503
    assert script.calls == 1


def test_a_create_that_is_not_json_is_not_retried() -> None:
    script = Script([reply(503)])
    with sync_client(script, FakeClock()) as client:
        client.post(CREATE, content=b"not json")
    assert script.calls == 1


def test_a_create_without_a_key_is_retried_only_before_it_was_sent() -> None:
    script = Script([httpx.ConnectError("x"), reply(200, {"job_id": "j"})])
    with sync_client(script, FakeClock()) as client:
        assert client.post(CREATE, json={"size_bytes": 5}).status_code == 200
    assert script.calls == 2
    script = Script([httpx.ReadError("x"), reply(200, {"job_id": "j"})])
    with sync_client(script, FakeClock()) as client, pytest.raises(NetworkError):
        client.post(CREATE, json={"size_bytes": 5})
    assert script.calls == 1


def test_a_keyed_create_is_retried_after_any_network_error() -> None:
    script = Script([httpx.ReadError("x"), reply(200, {"job_id": "j"})])
    with sync_client(script, FakeClock()) as client:
        assert client.post(CREATE, json=KEYED).status_code == 200
    assert script.calls == 2


@pytest.mark.anyio
async def test_async_a_create_without_a_key_is_not_retried() -> None:
    script = Script([reply(503)])
    async with async_client(script, FakeClock()) as client:
        await client.post(CREATE, json={"size_bytes": 5})
    assert script.calls == 1


# --- redirects are never followed (spec 7.2) ---


def _redirect(monkeypatch: pytest.MonkeyPatch) -> Script:
    script = Script(
        [httpx.Response(302, headers={"Location": "https://elsewhere.test/v1/account"})]
    )
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)
    return script


def test_a_redirect_is_an_error_and_is_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _redirect(monkeypatch)
    hs = Hushscript(TOKEN, base_url=BASE_URL, clock=FakeClock())
    with pytest.raises(ApiError) as raised:
        hs.balance()
    assert raised.value.status == 302
    assert script.calls == 1
    assert hs._http.follow_redirects is False
    assert hs._r2.follow_redirects is False


@pytest.mark.anyio
async def test_async_a_redirect_is_an_error_and_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _redirect(monkeypatch)
    hs = AsyncHushscript(TOKEN, base_url=BASE_URL, clock=FakeClock())
    with pytest.raises(ApiError) as raised:
        await hs.balance()
    assert raised.value.status == 302
    assert script.calls == 1
    assert hs._http.follow_redirects is False
    assert hs._r2.follow_redirects is False


# --- the part transport has its own client with no token ---


def test_direct_part_requests_carry_no_token_even_on_the_api_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), httpx.Response(200, headers={"ETag": '"abc"'})])
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    hs = Hushscript(TOKEN, base_url=BASE_URL, clock=FakeClock())
    response = hs._r2.put(
        f"{BASE_URL}/__r2/job_1/1?sig=x",
        content=b"abc",
        extensions={CLASS_EXTENSION: RetryClass.PART},
    )
    assert response.status_code == 200
    assert script.calls == 2
    assert all("authorization" not in r.headers for r in script.requests)


# --- pacing and the clock ---


def test_the_bucket_gives_four_free_slots_to_racing_threads() -> None:
    bucket = TokenBucket(FakeClock())
    waits: list[float] = []
    lock = threading.Lock()

    def reserve() -> None:
        wait = bucket.reserve()
        with lock:
            waits.append(wait)

    threads = [threading.Thread(target=reserve) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(waits) == [0.0] * 4 + [60.0] * 4 + [120.0] * 4


def test_the_system_clock_wait_wakes_on_the_event_and_otherwise_times_out() -> None:
    clock = SystemClock()
    stop = threading.Event()
    assert clock.wait(stop, 0.01) is False
    stop.set()
    assert clock.wait(stop, 30) is True
