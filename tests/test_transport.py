from __future__ import annotations

import logging

import httpx
import pytest

from conftest import TOKEN
from helpers import (
    BASE_URL,
    FakeClock,
    Script,
    async_client,
    error_body,
    reply,
    settings_for,
    sync_client,
)
from hushscript import NetworkError, OutcomeUnknownError
from hushscript._http import (
    ANONYMOUS_EXTENSION,
    CLASS_EXTENSION,
    LABEL_EXTENSION,
    RetryingTransport,
)
from hushscript._retry import RetryClass

RATE_LIMITED = error_body("rate_limited", 5000)
CONNECT = httpx.ConnectError("refused")
READ = httpx.ReadError("reset")


def test_does_not_wait_for_a_retry_after_above_60_seconds() -> None:
    script, clock = Script([reply(429, RATE_LIMITED, {"Retry-After": "61"})]), FakeClock()
    with sync_client(script, clock) as client:
        response = client.get("/v1/account")
    assert response.status_code == 429
    assert script.calls == 1
    assert clock.sleeps == []


def test_waits_exactly_the_retry_after_and_then_succeeds() -> None:
    script = Script([reply(429, RATE_LIMITED, {"Retry-After": "2"}), reply(200, {"ok": True})])
    clock = FakeClock()
    with sync_client(script, clock) as client:
        assert client.get("/v1/account").status_code == 200
    assert clock.sleeps == [2.0]


def test_a_get_retries_503_three_times_then_returns_the_last_response() -> None:
    script, clock = Script([reply(503)]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.get("/v1/jobs").status_code == 503
    assert script.calls == 4
    assert len(clock.sleeps) == 3
    assert all(0 <= delay <= 8 for delay in clock.sleeps)


def test_max_retries_zero_sends_once() -> None:
    script, clock = Script([reply(503)]), FakeClock()
    with sync_client(script, clock, max_retries=0) as client:
        client.get("/v1/jobs")
    assert script.calls == 1


def test_a_purchase_retries_502_once_with_the_same_body() -> None:
    script, clock = Script([reply(502), reply(502)]), FakeClock()
    with sync_client(script, clock, max_retries=5) as client:
        response = client.post(
            "/v1/billing/purchase", json={"pack": "300min", "idempotency_key": "k"}
        )
    assert response.status_code == 502
    assert script.calls == 2
    assert script.requests[0].content == script.requests[1].content


def test_a_purchase_never_retries_a_403() -> None:
    script, clock = Script([reply(403, error_body("pat_purchase_requires_app", 4021))]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.post("/v1/billing/purchase", json={}).status_code == 403
    assert script.calls == 1
    assert clock.sleeps == []


def test_a_purchase_retries_a_network_error_once() -> None:
    script, clock = Script([READ, reply(200, {"balance_seconds": 1})]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.post("/v1/billing/purchase", json={}).status_code == 200
    assert script.calls == 2


def test_claim_is_never_retried_and_a_lost_response_is_unknown() -> None:
    script, clock = Script([READ]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(OutcomeUnknownError) as raised:
        client.post("/v1/agent/accounts/sg_1/claim", json={})
    assert script.calls == 1
    assert raised.value.hint is not None
    assert "The claim may have succeeded" in raised.value.hint
    assert isinstance(raised.value.__cause__, httpx.ReadError)


def test_rotate_is_never_retried_and_a_lost_response_is_unknown() -> None:
    script, clock = Script([httpx.ReadTimeout("slow")]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(OutcomeUnknownError) as raised:
        client.post("/v1/agent/credentials/rotate", json={})
    assert script.calls == 1
    assert raised.value.hint is not None
    assert "The old token may already be revoked" in raised.value.hint


def test_a_connect_failure_on_claim_is_a_plain_network_error() -> None:
    script, clock = Script([CONNECT]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(NetworkError) as raised:
        client.post("/v1/agent/accounts/sg_1/claim", json={})
    assert not isinstance(raised.value, OutcomeUnknownError)
    assert script.calls == 1


def test_other_mutations_retry_only_failures_before_the_request_was_sent() -> None:
    script, clock = Script([CONNECT, reply(200, {})]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.patch("/v1/org/members/u1", json={}).status_code == 200
    assert script.calls == 2
    lost = Script([READ])
    with sync_client(lost, FakeClock()) as client, pytest.raises(NetworkError):
        client.patch("/v1/org/members/u1", json={})
    assert lost.calls == 1


def test_network_errors_are_retried_for_gets_and_then_raised() -> None:
    script, clock = Script([CONNECT]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(NetworkError, match="Could not reach"):
        client.get("/v1/account")
    assert script.calls == 4
    assert len(clock.sleeps) == 3


def test_create_backs_off_15_30_60_without_a_retry_after() -> None:
    script, clock = Script([reply(429, RATE_LIMITED)]), FakeClock()
    with sync_client(script, clock, max_retries=5) as client:
        assert client.post("/v1/uploads", json={"idempotency_key": "k" * 20}).status_code == 429
    assert clock.sleeps == [15.0, 30.0, 60.0]
    assert script.calls == 4


def test_create_waits_30_seconds_ten_tries_on_too_many_active_jobs() -> None:
    script, clock = Script([reply(429, error_body("too_many_active_jobs", 5001))]), FakeClock()
    with sync_client(script, clock, max_retries=1) as client:
        response = client.post("/v1/uploads", json={"idempotency_key": "k" * 20})
    assert response.json()["error"] == "too_many_active_jobs"
    assert script.calls == 10
    assert clock.sleeps == [30.0] * 9


def test_max_retries_zero_disables_the_active_jobs_wait() -> None:
    script = Script([reply(429, error_body("too_many_active_jobs", 5001))])
    with sync_client(script, FakeClock(), max_retries=0) as client:
        client.post("/v1/uploads", json={"idempotency_key": "k" * 20})
    assert script.calls == 1


def test_create_with_a_non_json_429_backs_off_too() -> None:
    script, clock = Script([reply(429), reply(200, {"ok": True})]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.post("/v1/uploads", json={"idempotency_key": "k" * 20}).status_code == 200
    assert clock.sleeps == [15.0]


@pytest.mark.parametrize(
    ("method", "path"),
    [("PUT", "/v1/uploads/j1/parts/2"), ("POST", "/v1/uploads/j1/complete")],
)
def test_part_and_complete_retry_a_500(method: str, path: str) -> None:
    script, clock = Script([reply(500), reply(200, {})]), FakeClock()
    with sync_client(script, clock) as client:
        assert client.request(method, path, content=b"x").status_code == 200
    assert script.calls == 2


def test_the_authorization_header_is_added_per_request() -> None:
    script, clock = Script([reply(200, {})]), FakeClock()
    with sync_client(script, clock, token=TOKEN) as client:
        client.get("/v1/account")
        assert "authorization" not in client.headers
    assert script.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"


def test_an_anonymous_request_and_a_client_without_a_token_send_no_authorization() -> None:
    script, clock = Script([reply(200, {})]), FakeClock()
    with sync_client(script, clock, token=TOKEN) as client:
        client.get("/v1/account", extensions={ANONYMOUS_EXTENSION: True})
    with sync_client(script, clock) as client:
        client.get("/v1/account")
    assert all("authorization" not in request.headers for request in script.requests)


def test_a_class_extension_applies_to_a_request_to_another_host() -> None:
    script, clock = Script([reply(500), reply(200, {})]), FakeClock()
    with sync_client(script, clock) as client:
        response = client.put(
            "https://r2.example.com/part",
            content=b"x",
            extensions={CLASS_EXTENSION: RetryClass.PART},
        )
    assert response.status_code == 200
    assert script.calls == 2


def test_a_class_extension_cannot_relabel_an_api_request() -> None:
    script, clock = Script([READ]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(OutcomeUnknownError):
        client.post(
            "/v1/agent/credentials/rotate", json={}, extensions={CLASS_EXTENSION: RetryClass.SAFE}
        )
    assert script.calls == 1


def test_a_path_that_names_an_api_route_on_another_host_is_not_that_route() -> None:
    script, clock = Script([READ]), FakeClock()
    with sync_client(script, clock) as client, pytest.raises(NetworkError) as raised:
        client.post("https://r2.example.com/v1/agent/credentials/rotate", json={})
    assert not isinstance(raised.value, OutcomeUnknownError)
    assert script.calls == 1


@pytest.mark.parametrize("url", ["https://r2.example.com/part", "http://127.0.0.1:4011/v1/account"])
def test_the_token_goes_only_to_the_base_url_host(url: str) -> None:
    script, clock = Script([reply(200, {})]), FakeClock()
    with sync_client(script, clock, token=TOKEN) as client:
        client.get(url)
        client.get("/v1/account")
    assert "authorization" not in script.requests[0].headers
    assert script.requests[1].headers["Authorization"] == f"Bearer {TOKEN}"


def test_debug_logging_writes_one_line_per_attempt_without_the_query(
    caplog: pytest.LogCaptureFixture,
) -> None:
    script = Script([reply(503), reply(200, {})])
    with (
        caplog.at_level(logging.DEBUG, logger="hushscript"),
        sync_client(script, FakeClock(), level="debug", token=TOKEN) as client,
    ):
        client.get("/v1/jobs?secret=abc")
        client.put(
            "https://r2.example.com/signed?X-Signature=zzz",
            content=b"x",
            extensions={LABEL_EXTENSION: "r2:part/3", CLASS_EXTENSION: RetryClass.PART},
        )
    lines = [record.getMessage() for record in caplog.records]
    assert lines[0].startswith("hushscript GET /v1/jobs error") is False
    assert lines[0].startswith("hushscript GET /v1/jobs 503 attempt=1")
    assert "retry_in=" in lines[0]
    assert lines[1].startswith("hushscript GET /v1/jobs 200 attempt=2")
    assert lines[2].startswith("hushscript PUT r2:part/3 200 attempt=1")
    joined = "\n".join(lines)
    assert "secret" not in joined
    assert "X-Signature" not in joined
    assert TOKEN not in joined


def test_logging_is_silent_by_default(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.DEBUG, logger="hushscript"),
        sync_client(Script([reply(200, {})]), FakeClock()) as client,
    ):
        client.get("/v1/account")
    assert caplog.records == []


def test_a_failed_attempt_is_logged_as_an_error(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.DEBUG, logger="hushscript"),
        sync_client(Script([CONNECT]), FakeClock(), level="debug", max_retries=0) as client,
        pytest.raises(NetworkError),
    ):
        client.get("/v1/account")
    assert "GET /v1/account error attempt=1" in caplog.records[0].getMessage()


@pytest.mark.anyio
async def test_async_waits_the_retry_after_and_not_above_sixty() -> None:
    script = Script([reply(429, RATE_LIMITED, {"Retry-After": "3"}), reply(200, {})])
    clock = FakeClock()
    async with async_client(script, clock) as client:
        assert (await client.get("/v1/account")).status_code == 200
    assert clock.sleeps == [3.0]
    long = Script([reply(429, RATE_LIMITED, {"Retry-After": "61"})])
    async with async_client(long, FakeClock()) as client:
        assert (await client.get("/v1/account")).status_code == 429
    assert long.calls == 1


@pytest.mark.anyio
async def test_async_purchase_cap_and_claim_never() -> None:
    purchase = Script([reply(502)])
    async with async_client(purchase, FakeClock(), max_retries=5) as client:
        assert (await client.post("/v1/billing/purchase", json={})).status_code == 502
    assert purchase.calls == 2
    claim = Script([READ])
    async with async_client(claim, FakeClock()) as client:
        with pytest.raises(OutcomeUnknownError):
            await client.post("/v1/agent/accounts/sg_1/claim", json={})
    assert claim.calls == 1


@pytest.mark.anyio
async def test_async_network_errors_and_create_pacing() -> None:
    script = Script([CONNECT])
    clock = FakeClock()
    async with async_client(script, clock) as client:
        with pytest.raises(NetworkError):
            await client.get("/v1/account")
    assert script.calls == 4
    create, create_clock = Script([reply(429, RATE_LIMITED)]), FakeClock()
    async with async_client(create, create_clock, max_retries=5) as client:
        assert (
            await client.post("/v1/uploads", json={"idempotency_key": "k" * 20})
        ).status_code == 429
    assert create_clock.sleeps == [15.0, 30.0, 60.0]
    active = Script([reply(429, error_body("too_many_active_jobs", 5001))])
    async with async_client(active, FakeClock()) as client:
        await client.post("/v1/uploads", json={"idempotency_key": "k" * 20})
    assert active.calls == 10


STATUSES = [429, 500, 502, 503, 504]


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/agent/accounts/sg_1/claim"),
        ("POST", "/v1/agent/credentials/rotate"),
        ("POST", "/v1/agent/accounts"),
        ("POST", "/v1/billing/cards/default"),
        ("PUT", "/v1/billing/cards/default"),
        ("PATCH", "/v1/org/members/u1"),
    ],
)
def test_claim_rotate_signup_and_other_mutations_never_retry_on_a_status(
    method: str, path: str, status: int
) -> None:
    script, clock = Script([reply(status), reply(200, {})]), FakeClock()
    with sync_client(script, clock, max_retries=5) as client:
        assert client.request(method, path, json={}).status_code == status
    assert script.calls == 1
    assert clock.sleeps == []


@pytest.mark.parametrize(("status", "calls"), [(502, 2), (503, 2), (500, 1), (504, 1), (429, 1)])
def test_a_purchase_makes_at_most_two_calls_and_retries_only_502_and_503(
    status: int, calls: int
) -> None:
    script = Script([reply(status)])
    with sync_client(script, FakeClock(), max_retries=5) as client:
        client.post("/v1/billing/purchase", json={})
    assert script.calls == calls


def test_a_purchase_makes_at_most_two_calls_on_network_errors() -> None:
    script = Script([READ])
    with sync_client(script, FakeClock(), max_retries=5) as client, pytest.raises(NetworkError):
        client.post("/v1/billing/setup-session", json={})
    assert script.calls == 2


@pytest.mark.parametrize("status", [501, 505, 507])
def test_a_get_does_not_retry_other_5xx(status: int) -> None:
    script = Script([reply(status)])
    with sync_client(script, FakeClock()) as client:
        assert client.get("/v1/uploads/j1/part-urls").status_code == status
    assert script.calls == 1


@pytest.mark.parametrize("status", STATUSES)
def test_get_heartbeat_and_part_urls_retry_the_listed_statuses(status: int) -> None:
    for method, path in (
        ("GET", "/v1/account"),
        ("POST", "/v1/uploads/j1/heartbeat"),
        ("GET", "/v1/uploads/j1/part-urls"),
    ):
        script = Script([reply(status), reply(200, {})])
        with sync_client(script, FakeClock()) as client:
            assert client.request(method, path).status_code == 200
        assert script.calls == 2


@pytest.mark.parametrize("status", [500, 502, 503, 504])
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/account"),
        ("PUT", "/v1/uploads/j1/parts/1"),
        ("POST", "/v1/uploads/j1/complete"),
        ("POST", "/v1/uploads"),
        ("POST", "/v1/billing/purchase"),
    ],
)
def test_a_retry_after_above_60_on_a_5xx_is_returned_at_once(
    method: str, path: str, status: int
) -> None:
    script, clock = Script([reply(status, headers={"Retry-After": "61"})]), FakeClock()
    with sync_client(script, clock) as client:
        response = client.request(method, path, content=b"x")
    assert response.status_code == status
    assert response.headers["Retry-After"] == "61"
    assert script.calls == 1
    assert clock.sleeps == []


def test_the_create_429_schedule_counts_only_429s_after_other_retries() -> None:
    script = Script(
        [reply(500), reply(429, RATE_LIMITED), reply(429, RATE_LIMITED), reply(200, {})]
    )
    clock = FakeClock()
    with sync_client(script, clock, max_retries=5) as client:
        assert client.post("/v1/uploads", json={"idempotency_key": "k" * 20}).status_code == 200
    assert script.calls == 4
    assert clock.sleeps[1:] == [15.0, 30.0]


def test_the_create_429_schedule_still_ends_after_three_waits_following_a_500() -> None:
    script = Script([reply(500), reply(429, RATE_LIMITED)])
    clock = FakeClock()
    with sync_client(script, clock, max_retries=9) as client:
        assert client.post("/v1/uploads", json={"idempotency_key": "k" * 20}).status_code == 429
    assert clock.sleeps[1:] == [15.0, 30.0, 60.0]


def test_the_active_jobs_wait_counts_only_active_jobs_429s() -> None:
    active = reply(429, error_body("too_many_active_jobs", 5001))
    script = Script([reply(429, RATE_LIMITED), reply(500), active])
    clock = FakeClock()
    with sync_client(script, clock, max_retries=3) as client:
        assert client.post("/v1/uploads", json={"idempotency_key": "k" * 20}).status_code == 429
    assert script.calls == 12
    assert clock.sleeps[2:] == [30.0] * 9


def test_a_token_unset_since_an_earlier_attempt_is_not_sent_on_the_retry() -> None:
    clock = FakeClock()
    settings = settings_for(clock, token=TOKEN)
    assert settings.credentials is not None
    credentials = settings.credentials
    sent: list[str | None] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get("authorization"))
        if len(sent) == 1:
            credentials._tokens.clear()
            return reply(503)
        return reply(200, {})

    with httpx.Client(
        base_url=BASE_URL, transport=RetryingTransport(httpx.MockTransport(handle), settings)
    ) as client:
        assert client.get("/v1/account").status_code == 200
    assert sent == [f"Bearer {TOKEN}", None]
