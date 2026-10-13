from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

import hushscript._client as client_module
import hushscript.resources.agent as agent_module
from conftest import TOKEN
from helpers import BASE_URL, FakeClock, error_body, reply, stand_in
from hushscript import (
    AgentInfo,
    ApiError,
    AsyncHushscript,
    ConflictError,
    Hushscript,
    NetworkError,
    OutcomeUnknownError,
    PreflightError,
    ValidationError,
)
from routes import Routes, async_hs_on, hs_on

if TYPE_CHECKING:
    from collections.abc import Callable

NEW_TOKEN = "hsr1:eu:pat." + "ab" * 16 + "." + "cd" * 32
CLAIM_HINT = (
    "The claim may have succeeded. Retrying will fail with agent_claim_invalid. "
    "If you have no token, contact support with the signup id."
)
ROTATE_HINT = (
    "The old token may already be revoked. Try a request with it; if it fails, "
    "the new token was lost and the account needs support."
)
SIGNUP = {
    "signup_id": "sg_1",
    "claim_secret": "cs_secret",
    "checkout_url": "https://checkout.test/pay",
    "pack": "45min",
    "amount": 599,
    "currency": "USD",
    "expires_at": 1_700_001_800,
}
CLAIMED = {
    "user_id": "u_1",
    "pat": NEW_TOKEN,
    "scopes": ["transcribe", "billing"],
    "balance_seconds": 2700,
}
ROTATED = {
    "pat": NEW_TOKEN,
    "pat_id": "pat_9",
    "scopes": ["transcribe"],
    "expires_at": 1_800_000_000,
}
AGENT = AgentInfo(name="Example agent", platform="custom")


def static(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> Routes:
    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
    return routes


def signup(**overrides: object) -> object:
    arguments: dict[str, object] = {
        "email": "agent@example.com",
        "pack": "45min",
        "accept_terms": "2026-10-01",
        "agent": AGENT,
        "base_url": BASE_URL,
        "clock": FakeClock(),
    }
    return Hushscript.agent_signup(**{**arguments, **overrides})  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def claim(**overrides: object) -> object:
    arguments: dict[str, object] = {"base_url": BASE_URL, "clock": FakeClock()}
    return Hushscript.agent_claim("sg_1", "cs_secret", **{**arguments, **overrides})  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


# --- signup ---


@pytest.mark.parametrize("terms", [None, "", "  ", 5])
def test_signup_without_accept_terms_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch, terms: object
) -> None:
    routes = static(monkeypatch, lambda _r: reply(200, SIGNUP))
    with pytest.raises(ValidationError) as raised:
        signup(accept_terms=terms)
    assert (raised.value.code, raised.value.status) == ("accept_terms_required", None)
    assert routes.requests == []


@pytest.mark.parametrize("status", [200, 201])
def test_signup_sends_the_request_and_maps_any_2xx(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    routes = static(monkeypatch, lambda _r: reply(status, SIGNUP))
    result = signup(agent=AgentInfo("A", "p", "https://a.test"), data_region="eu", dry_run=True)
    assert json.loads(routes.requests[0].content) == {
        "contact_email": "agent@example.com",
        "pack_id": "45min",
        "accept_terms_version": "2026-10-01",
        "agent": {"name": "A", "platform": "p", "contact_url": "https://a.test"},
        "data_region": "eu",
        "dry_run": True,
    }
    assert (result.signup_id, result.claim_secret, result.checkout_url) == (  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        "sg_1",
        "cs_secret",
        "https://checkout.test/pay",
    )
    assert result.price.formatted == "$5.99"  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert result.expires_at.year == 2023  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]


def test_signup_sends_no_token_even_when_the_environment_has_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HUSHSCRIPT_TOKEN", TOKEN)
    routes = static(monkeypatch, lambda _r: reply(200, SIGNUP))
    signup()
    claim_routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    claim()
    for request in (*routes.requests, *claim_routes.requests):
        assert "authorization" not in request.headers


@pytest.mark.parametrize("body", [{}, {**SIGNUP, "amount": "5"}, {**SIGNUP, "expires_at": -1}, []])
def test_an_unusable_signup_answer_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    static(monkeypatch, lambda _r: reply(201, body))
    with pytest.raises(ApiError) as raised:
        signup()
    assert (raised.value.code, raised.value.status) == ("bad_response", 201)


def test_a_signup_is_never_retried_and_a_lost_answer_is_outcome_unknown_without_a_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = static(monkeypatch, lambda _r: reply(503, error_body("internal_error", 9000)))
    with pytest.raises(ApiError) as refusal:
        signup()
    assert type(refusal.value) is ApiError
    assert (refusal.value.code, refusal.value.status) == ("internal_error", 503)
    assert len(routes.requests) == 1

    def lost(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("reset")

    routes = static(monkeypatch, lost)
    with pytest.raises(OutcomeUnknownError) as raised:
        signup()
    assert raised.value.hint is None
    assert (raised.value.code, raised.value.status) == ("outcome_unknown", None)
    assert stand_in(raised.value) == "ReadError: reset"
    assert len(routes.requests) == 1


def test_a_policy_version_error_quotes_the_current_version(monkeypatch: pytest.MonkeyPatch) -> None:
    static(
        monkeypatch,
        lambda _r: reply(
            422,
            error_body("policy_version_stale", 1043, details={"current_version": "2026-11-01"}),
        ),
    )
    with pytest.raises(ValidationError) as raised:
        signup()
    assert raised.value.details == {"current_version": "2026-11-01"}
    assert (raised.value.code, raised.value.status) == ("policy_version_stale", 422)
    assert raised.value.hint == ("Accept the current terms version: 2026-11-01.")


# --- claim ---


def test_a_claim_returns_the_account_and_sends_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    account = claim()
    assert account.token == NEW_TOKEN  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert account.user_id == "u_1"  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert account.scopes == ["transcribe", "billing"]  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert (account.balance.seconds, account.balance.minutes) == (2700, 45)  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert routes.requests[0].url.path == "/v1/agent/accounts/sg_1/claim"
    assert json.loads(routes.requests[0].content) == {"claim_secret": "cs_secret"}


def test_a_claim_before_the_checkout_is_paid_is_a_conflict_without_the_job_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    static(monkeypatch, lambda _r: reply(409, error_body("wrong_state", 4001)))
    with pytest.raises(ConflictError) as raised:
        claim()
    assert raised.value.code == "wrong_state"
    assert raised.value.hint is None


@pytest.mark.parametrize("signup_id", ["", ".", "..", "\ud800", None, 42])
def test_a_signup_id_that_cannot_be_a_path_segment_is_refused(
    monkeypatch: pytest.MonkeyPatch, signup_id: object
) -> None:
    routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    with pytest.raises(PreflightError) as raised:
        Hushscript.agent_claim(signup_id, "s", base_url=BASE_URL)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


def test_a_signup_id_is_percent_encoded(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    Hushscript.agent_claim("a/b?c", "s", base_url=BASE_URL)
    assert routes.requests[0].url.raw_path == b"/v1/agent/accounts/a%2Fb%3Fc/claim"


def test_a_lost_claim_is_outcome_unknown_with_the_hint_and_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def lost(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("reset")

    routes = static(monkeypatch, lost)
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert raised.value.hint == CLAIM_HINT
    assert stand_in(raised.value) == "ReadError: reset"
    assert len(routes.requests) == 1


def test_a_claim_that_never_connected_is_a_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    static(monkeypatch, refused)
    with pytest.raises(NetworkError):
        claim()


@pytest.mark.parametrize("status", [200, 201, 202, 203])
@pytest.mark.parametrize(
    ("body", "received"),
    [
        ({"user_id": "u", "scopes": [], "balance_seconds": 0}, None),
        ({**CLAIMED, "pat": 5}, None),
        ({**CLAIMED, "pat": ""}, None),
        ({**CLAIMED, "pat": " \t "}, None),
        ({**CLAIMED, "pat": "not-a-token"}, "not-a-token"),
        ({**CLAIMED, "pat": " " + NEW_TOKEN}, " " + NEW_TOKEN),
        ({**CLAIMED, "pat": "hsr1:ünï"}, "hsr1:ünï"),
        ({**CLAIMED, "user_id": 5}, NEW_TOKEN),
        ({**CLAIMED, "scopes": "billing"}, NEW_TOKEN),
        ({**CLAIMED, "scopes": [1]}, NEW_TOKEN),
        ({**CLAIMED, "balance_seconds": 1.5}, NEW_TOKEN),
        ([NEW_TOKEN], None),
    ],
)
def test_an_unusable_2xx_claim_is_a_lost_credential_that_keeps_what_it_saw(
    monkeypatch: pytest.MonkeyPatch, status: int, body: object, received: str | None
) -> None:
    routes = static(monkeypatch, lambda _r: reply(status, body))
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert raised.value.hint == CLAIM_HINT
    assert raised.value.received_token == received
    assert isinstance(raised.value.__cause__, ApiError)
    assert raised.value.__cause__.code == "bad_response"
    assert len(routes.requests) == 1


@pytest.mark.parametrize("seconds", [-1, 2**63, 10**400])
def test_a_claim_whose_balance_is_not_a_non_negative_int64_is_a_lost_credential(
    monkeypatch: pytest.MonkeyPatch, seconds: int
) -> None:
    static(monkeypatch, lambda _r: reply(201, {**CLAIMED, "balance_seconds": seconds}))
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert raised.value.hint == CLAIM_HINT
    assert raised.value.received_token == NEW_TOKEN


@pytest.mark.parametrize("seconds", [0, 2**63 - 1])
def test_a_claim_with_a_balance_at_the_ends_of_the_range_is_usable(
    monkeypatch: pytest.MonkeyPatch, seconds: int
) -> None:
    static(monkeypatch, lambda _r: reply(201, {**CLAIMED, "balance_seconds": seconds}))
    assert claim().balance.seconds == seconds  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]


@pytest.mark.parametrize("answer", [httpx.Response(204), httpx.Response(200, content=b"nope")])
def test_a_claim_with_no_json_body_is_a_lost_credential(
    monkeypatch: pytest.MonkeyPatch, answer: httpx.Response
) -> None:
    static(monkeypatch, lambda _r: answer)
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert raised.value.received_token is None


def test_the_token_of_a_claim_is_scrubbed_from_the_texts_of_its_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    odd = "hsr1-odd\u00e9-SECRET-text"
    static(monkeypatch, lambda _r: reply(201, {**CLAIMED, "pat": odd}))
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert odd not in raised.value.message
    assert odd not in str(raised.value)
    assert odd not in repr(raised.value)
    assert raised.value.received_token == odd


# --- rotate ---


def test_a_rotation_returns_the_token_and_the_client_sends_it_from_then_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return reply(201, ROTATED)
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = hs_on(monkeypatch, handler)
    rotated = hs.agent.rotate_token()
    assert (rotated.token, rotated.token_id, rotated.scopes) == (NEW_TOKEN, "pat_9", ["transcribe"])
    assert rotated.expires_at is not None
    assert rotated.expires_at.year == 2027
    hs.balance()
    assert routes.requests[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert routes.requests[1].headers["authorization"] == f"Bearer {NEW_TOKEN}"


def test_a_rotation_answer_with_a_5000_digit_integer_still_yields_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps(ROTATED)[:-1].encode() + b',"unused":' + b"9" * 5000 + b"}"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return httpx.Response(201, content=body)
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = hs_on(monkeypatch, handler)
    assert hs.agent.rotate_token().token == NEW_TOKEN
    hs.balance()
    assert routes.requests[1].headers["authorization"] == f"Bearer {NEW_TOKEN}"


def test_a_rotation_answer_with_a_5000_digit_integer_and_a_bad_field_keeps_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps({**ROTATED, "pat_id": 5})[:-1].encode() + b',"unused":' + b"9" * 5000 + b"}"
    hs, _routes = hs_on(monkeypatch, lambda _r: httpx.Response(201, content=body))
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    assert raised.value.received_token == NEW_TOKEN


def test_a_rotation_without_an_expiry_never_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {key: value for key, value in ROTATED.items() if key != "expires_at"}
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, body))
    assert hs.agent.rotate_token().expires_at is None
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, {**body, "expires_at": None}))
    assert hs.agent.rotate_token().expires_at is None


def test_a_rotation_applies_to_a_request_that_was_already_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    steps: list[httpx.Response] = [
        reply(500),
        reply(200, {"balance_seconds": 1, "held_seconds": 0}),
    ]
    clients: list[Hushscript] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return reply(201, ROTATED)
        seen.append(request.headers["authorization"])
        return steps.pop(0)

    class Rotating(FakeClock):
        def sleep(self, seconds: float) -> None:
            super().sleep(seconds)
            clients[0].agent.rotate_token()  # a rotation lands while the retry waits

    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    clients.append(Hushscript(TOKEN, base_url=BASE_URL, clock=Rotating()))
    clients[0].balance()
    assert seen == [f"Bearer {TOKEN}", f"Bearer {NEW_TOKEN}"]


def test_a_lost_rotation_keeps_the_old_token_and_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            raise httpx.ReadError("reset")
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = hs_on(monkeypatch, handler)
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    assert raised.value.hint == ROTATE_HINT
    assert len(routes.requests) == 1
    hs.balance()
    assert routes.requests[1].headers["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("status", [200, 201, 202])
@pytest.mark.parametrize(
    ("body", "swapped", "received"),
    [
        ({"pat_id": "p", "scopes": []}, False, None),
        ({**ROTATED, "pat": ""}, False, None),
        ({**ROTATED, "pat": "  "}, False, None),
        ({**ROTATED, "pat": "not-a-token"}, False, "not-a-token"),
        ({**ROTATED, "expires_at": "soon"}, False, NEW_TOKEN),
        ({**ROTATED, "expires_at": -5}, False, NEW_TOKEN),
        ({**ROTATED, "expires_at": 1.5}, False, NEW_TOKEN),
        ({**ROTATED, "expires_at": 10**15}, False, NEW_TOKEN),
        ({**ROTATED, "pat_id": 5}, True, NEW_TOKEN),
        ({**ROTATED, "scopes": None}, True, NEW_TOKEN),
        ([], False, None),
    ],
)
def test_an_unusable_2xx_rotation_is_a_lost_credential(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: object,
    swapped: bool,  # noqa: FBT001  # a table column
    received: str | None,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return reply(status, body)
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = hs_on(monkeypatch, handler)
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    assert raised.value.hint == ROTATE_HINT
    assert raised.value.received_token == received
    hs.balance()
    sent = routes.requests[1].headers["authorization"]
    assert sent == f"Bearer {NEW_TOKEN if swapped else TOKEN}"


def test_a_rejected_rotation_is_an_ordinary_error(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, _ = hs_on(monkeypatch, lambda _r: reply(401, error_body("unauthorized", 2000)))
    with pytest.raises(ApiError) as raised:
        hs.agent.rotate_token()
    assert raised.value.code == "unauthorized"


def test_the_rotated_token_is_scrubbed_from_later_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    odd_token = "hsr1-odd-ROTATED-secret"
    steps = [reply(201, {**ROTATED, "pat": odd_token}), reply(500, error_body("x", 1))]
    hs, _ = hs_on(monkeypatch, lambda _r: steps.pop(0))
    hs.agent.rotate_token()
    assert hs._config.credentials.scrub(f"leak {odd_token}") == "leak hsr…[redacted]"  # pyright: ignore[reportPrivateUsage]
    assert hs._config.credentials.token == odd_token  # pyright: ignore[reportPrivateUsage]


@pytest.mark.anyio
async def test_the_async_agent_calls_match_the_sync_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/agent/accounts":
            return reply(201, SIGNUP)
        if path.endswith("/claim"):
            return reply(201, CLAIMED)
        return reply(201, ROTATED)

    hs, routes = async_hs_on(monkeypatch, handler)
    created = await AsyncHushscript.agent_signup(
        email="a@b.c", pack="45min", accept_terms="v1", agent=AGENT, base_url=BASE_URL
    )
    assert created.signup_id == "sg_1"
    account = await AsyncHushscript.agent_claim("sg_1", "s", base_url=BASE_URL)
    assert account.token == NEW_TOKEN
    rotated = await hs.agent.rotate_token()
    assert rotated.token == NEW_TOKEN
    assert "authorization" not in routes.requests[0].headers
    with pytest.raises(ValidationError):
        await AsyncHushscript.agent_signup(
            email="a@b.c", pack="45min", accept_terms="", agent=AGENT, base_url=BASE_URL
        )


@pytest.mark.anyio
async def test_async_a_rotation_returns_the_token_and_the_client_sends_it_from_then_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return reply(201, ROTATED)
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = async_hs_on(monkeypatch, handler)
    rotated = await hs.agent.rotate_token()
    assert (rotated.token, rotated.token_id, rotated.scopes) == (NEW_TOKEN, "pat_9", ["transcribe"])
    assert rotated.expires_at is not None
    assert rotated.expires_at.year == 2027
    await hs.balance()
    assert routes.requests[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert routes.requests[1].headers["authorization"] == f"Bearer {NEW_TOKEN}"


@pytest.mark.anyio
async def test_an_async_lost_claim_is_outcome_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def lost(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("reset")

    routes = Routes(lost)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
    with pytest.raises(OutcomeUnknownError) as raised:
        await AsyncHushscript.agent_claim("sg_1", "s", base_url=BASE_URL)
    assert raised.value.hint == CLAIM_HINT
    assert len(routes.requests) == 1


# --- the SDK failing on a 2xx answer (R61, spec 7.4) ---

STRAY = f"stray failure with {NEW_TOKEN} in it"
LONE = "hsr\u2026\ud800"


def escaped(status: int, body: object) -> httpx.Response:
    """A JSON answer written with escapes, as a server writes a lone surrogate."""
    return httpx.Response(
        status, content=json.dumps(body).encode(), headers={"content-type": "application/json"}
    )


def stray(*_args: object, **_kwargs: object) -> object:
    raise TypeError(STRAY)


def check_stray_loss(error: OutcomeUnknownError, hint: str) -> None:
    assert error.hint == hint
    assert error.received_token == NEW_TOKEN
    cause = error.__cause__
    assert cause is not None
    assert "TypeError" in str(cause)
    assert NEW_TOKEN not in str(cause) + str(error) + repr(error)
    assert error.__context__ is None


def test_an_sdk_failure_reading_a_claim_answer_is_a_lost_credential_with_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    static(monkeypatch, lambda _r: reply(201, CLAIMED))
    monkeypatch.setattr(agent_module, "account_of", stray)
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    check_stray_loss(raised.value, CLAIM_HINT)


@pytest.mark.anyio
async def test_async_an_sdk_failure_reading_a_claim_answer_is_a_lost_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    static(monkeypatch, lambda _r: reply(201, CLAIMED))
    monkeypatch.setattr(agent_module, "account_of", stray)
    with pytest.raises(OutcomeUnknownError) as raised:
        await AsyncHushscript.agent_claim("sg_1", "s", base_url=BASE_URL)
    check_stray_loss(raised.value, CLAIM_HINT)


def test_an_sdk_failure_reading_a_rotation_answer_leaves_the_client_on_the_token_the_caller_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return reply(201, ROTATED)
        return reply(200, {"balance_seconds": 60, "held_seconds": 0})

    hs, routes = hs_on(monkeypatch, handler)
    monkeypatch.setattr(agent_module, "rotated_of", stray)
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    check_stray_loss(raised.value, ROTATE_HINT)
    hs.balance()
    assert routes.requests[1].headers["authorization"] == f"Bearer {raised.value.received_token}"


@pytest.mark.anyio
async def test_async_an_sdk_failure_reading_a_rotation_answer_is_a_lost_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = async_hs_on(monkeypatch, lambda _r: reply(201, ROTATED))
    monkeypatch.setattr(agent_module, "rotated_of", stray)
    with pytest.raises(OutcomeUnknownError) as raised:
        await hs.agent.rotate_token()
    check_stray_loss(raised.value, ROTATE_HINT)


def test_a_pat_with_a_lone_surrogate_in_a_claim_is_a_lost_credential_that_keeps_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    static(monkeypatch, lambda _r: escaped(201, {**CLAIMED, "pat": LONE}))
    with pytest.raises(OutcomeUnknownError) as raised:
        claim()
    assert raised.value.hint == CLAIM_HINT
    assert raised.value.received_token == LONE
    assert isinstance(raised.value.__cause__, ApiError)
    assert raised.value.__cause__.code == "bad_response"


def test_a_pat_with_a_lone_surrogate_in_a_rotation_is_never_stored_and_breaks_nothing_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/agent/credentials/rotate":
            return escaped(201, {**ROTATED, "pat": LONE})
        return reply(500, error_body("internal_error", 5000))

    hs, routes = hs_on(monkeypatch, handler)
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    assert raised.value.hint == ROTATE_HINT
    assert raised.value.received_token == LONE
    credentials = hs._config.credentials  # pyright: ignore[reportPrivateUsage]
    assert credentials.token == TOKEN
    assert credentials.scrub(f"echo {LONE}") == f"echo {LONE}"  # never registered
    with pytest.raises(ApiError) as later:
        hs.balance()
    assert later.value.status == 500
    assert routes.requests[1].headers["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("signup_id", ["", ".", "..", "\ud800", None, 42, 5])
@pytest.mark.anyio
async def test_async_claim_ids_are_invalid_before_any_request(
    monkeypatch: pytest.MonkeyPatch, signup_id: object
) -> None:
    routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    with pytest.raises(PreflightError) as raised:
        await AsyncHushscript.agent_claim(signup_id, "s", base_url=BASE_URL)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


@pytest.mark.anyio
async def test_async_claim_encodes_the_signup_id(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = static(monkeypatch, lambda _r: reply(201, CLAIMED))
    await AsyncHushscript.agent_claim("a/b?c#d", "s", base_url=BASE_URL)
    assert routes.requests[0].url.raw_path == b"/v1/agent/accounts/a%2Fb%3Fc%23d/claim"


@pytest.mark.anyio
async def test_async_signup_refusals_and_lost_answers_are_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def call() -> object:
        return await AsyncHushscript.agent_signup(
            email="a@b.c",
            pack="45min",
            accept_terms="2026-10-01",
            agent=AGENT,
            base_url=BASE_URL,
        )

    routes = static(monkeypatch, lambda _r: reply(503, error_body("internal_error", 9000)))
    with pytest.raises(ApiError) as raised:
        await call()
    assert type(raised.value) is ApiError
    assert (raised.value.code, raised.value.status) == ("internal_error", 503)
    assert len(routes.requests) == 1

    failure = httpx.ReadError("lost")

    def lost(_r: httpx.Request) -> httpx.Response:
        raise failure

    routes = static(monkeypatch, lost)
    with pytest.raises(OutcomeUnknownError) as unknown:
        await call()
    assert (unknown.value.code, unknown.value.status) == ("outcome_unknown", None)
    assert unknown.value.hint is None
    assert stand_in(unknown.value) == "ReadError: lost"
    assert len(routes.requests) == 1
