"""Nothing the client holds or hands out shows a token, a received token or a signed URL."""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
import pickle
import pprint
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import pytest

import hushscript._client as client_module
import hushscript.resources.agent as agent_module
from conftest import TOKEN
from fakeapi import FakeApi
from helpers import BASE_URL, FakeClock, reply
from hushscript import (
    AgentAccount,
    AgentInfo,
    AgentSignup,
    AsyncHushscript,
    Balance,
    Hushscript,
    HushscriptError,
    NetworkError,
    OutcomeUnknownError,
    Purchase,
    RotatedToken,
    UploadError,
)
from hushscript._redact import REDACTED, Credentials, Secret
from hushscript.money import to_money
from hushscript.transcribe.upload import Created, parse_created
from pipe import async_hs_for, hs_for, media
from routes import Routes, hs_on

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType

ODD = "hsr1-oddé-RECEIVED-SECRET"
CLAIM_SECRET = "cs_CLAIM-SECRET-VALUE"
PAT = "hsr1:eu:pat." + "ab" * 16 + "." + "cd" * 32
SIGNED = "https://acct.r2.example.com/b/part-1?X-Amz-Signature=SIGNED-SECRET&X-Amz-Expires=3600"


def shown(value: object) -> list[str]:
    """Every text a value can print itself as."""
    texts = [repr(value), str(value), f"{value}", f"{value!r}", pprint.pformat(value)]
    texts.append(repr(getattr(value, "__dict__", {})))
    texts.append(repr(vars(value)) if hasattr(value, "__dict__") else "")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        texts.append(repr(dataclasses.asdict(value)))
        texts.append(repr(dataclasses.astuple(value)))
    texts.append(repr(copy.copy(value)))
    texts.append(repr(copy.deepcopy(value)))
    texts.append(repr(pickle.loads(pickle.dumps(value))))  # noqa: S301  # our own value
    texts.append(pickle.dumps(value).decode("latin-1"))
    return texts


def lost_claim(monkeypatch: pytest.MonkeyPatch) -> OutcomeUnknownError:
    routes = Routes(
        lambda _r: reply(201, {"user_id": "u", "pat": ODD, "scopes": [], "balance_seconds": 0})
    )
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    with pytest.raises(OutcomeUnknownError) as raised:
        Hushscript.agent_claim("sg_1", "s", base_url=BASE_URL, clock=FakeClock())
    return raised.value


def test_a_received_token_is_on_the_error_and_nowhere_it_prints(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    error = lost_claim(monkeypatch)
    assert error.received_token == ODD
    for text in shown(error):
        assert ODD not in text
    assert ODD not in "".join(str(part) for part in error.args)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("t").error("failed: %s %r", error, error)
        logging.getLogger("t").error("with trace", exc_info=error)
    assert ODD not in caplog.text
    assert "redacted" in repr(error._received)  # pyright: ignore[reportPrivateUsage]


def test_a_pickled_error_loses_the_received_token_and_a_copy_keeps_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = lost_claim(monkeypatch)
    assert ODD.encode("utf-8") not in pickle.dumps(error)
    assert pickle.loads(pickle.dumps(error)).received_token is None  # noqa: S301
    assert copy.deepcopy(error).received_token == ODD
    assert copy.copy(error).received_token == ODD


@pytest.mark.parametrize("seen", ["", "   ", "\n\t"])
def test_an_empty_or_blank_received_token_is_none(seen: str) -> None:
    assert OutcomeUnknownError("x", received_token=seen).received_token is None
    assert OutcomeUnknownError("x").received_token is None


def test_a_secret_prints_the_marker_in_every_form() -> None:
    secret = Secret("TOP-SECRET")
    assert secret.reveal() == "TOP-SECRET"
    for text in (*shown(secret), f"{secret:>30}"):
        assert "TOP-SECRET" not in text
    assert str(secret) == REDACTED
    assert not Secret("")
    assert secret
    assert copy.deepcopy(secret) is secret


def test_credentials_show_no_token_in_any_form() -> None:
    credentials = Credentials(TOKEN)
    credentials.remember("another-secret")
    for text in (repr(credentials), str(credentials), pprint.pformat(credentials)):
        assert TOKEN not in text
        assert "another-secret" not in text
    with pytest.raises(TypeError):
        pickle.dumps(credentials)
    assert credentials.scrub("a another-secret b") == f"a {REDACTED} b"
    assert credentials.token == TOKEN  # remembering never changes what is sent


def test_the_signed_urls_of_an_upload_plan_are_held_in_secrets() -> None:
    created: Created = parse_created(
        {
            "job_id": "job_1",
            "state": "uploading",
            "upload": {
                "part_size_bytes": 10,
                "total_parts": 1,
                "part_urls": [{"n": 1, "url": SIGNED}],
                "next_part_number": None,
            },
        }
    )
    assert created.plan is not None
    for value in (created, created.plan, created.plan.urls):
        for text in shown(value):
            assert "SIGNED-SECRET" not in text


def test_the_client_and_the_objects_it_returns_print_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, {}))
    for value in (hs, hs.api, hs.jobs, hs.billing, hs.agent, hs._session, hs._config):  # pyright: ignore[reportPrivateUsage]
        for text in (repr(value), str(value), pprint.pformat(value)):
            assert TOKEN not in text
    for result in (Purchase(60, 1), Balance(1, 0, 0, None, None)):
        for text in shown(result):
            assert TOKEN not in text


def test_a_token_in_an_error_message_is_redacted_whatever_its_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(
        monkeypatch,
        lambda _r: httpx.Response(
            400, json={"error": "bad_request", "code": 1, "details": {"echo": TOKEN}}
        ),
    )
    with pytest.raises(Exception) as raised:  # noqa: PT011
        hs.buy("300min")
    texts: list[Any] = [
        str(raised.value),
        repr(raised.value),
        repr(getattr(raised.value, "details", {})),
    ]
    assert all(TOKEN not in text for text in texts)


BALANCE = Balance(1, 0, 0, None, None)


def with_secrets() -> list[tuple[object, str]]:
    """Each result that hands the caller a secret, with the secret it holds."""
    return [
        (AgentAccount(TOKEN, "u", ["a"], BALANCE), TOKEN),
        (RotatedToken(TOKEN, "id", ["a"], None), TOKEN),
        (
            AgentSignup(
                "sg_1",
                CLAIM_SECRET,
                "https://checkout.test/pay",
                to_money(599, "USD"),
                datetime.fromtimestamp(1_700_001_800, tz=UTC),
            ),
            CLAIM_SECRET,
        ),
    ]


@pytest.mark.parametrize(("result", "secret"), with_secrets())
def test_a_result_with_a_secret_prints_the_marker_and_serializes_the_value(
    result: Any,  # the three result types share only this
    secret: str,
) -> None:
    for text in (repr(result), str(result), f"{result}", pprint.pformat(result), repr([result])):
        assert secret not in text
        assert "[redacted]" in text
    assert repr(copy.deepcopy(result)) == repr(result)
    name = "claim_secret" if isinstance(result, AgentSignup) else "token"
    assert getattr(result, name) == secret
    assert f"{name}={REDACTED}" in repr(result)
    # a deliberate export carries the value
    assert dataclasses.asdict(result)[name] == secret
    assert secret.encode() in pickle.dumps(result)
    assert json.dumps(dataclasses.asdict(result), default=str).count(secret) == 1


def sdk_locals(error: BaseException) -> Iterator[tuple[str, str, object]]:
    """Every local of every SDK-owned frame (module under `hushscript`) on the traceback of
    `error` and of what it was raised from or while handling. The HTTP library's frames are not
    the SDK's and are not walked."""
    seen: set[int] = set()
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        tb: TracebackType | None = current.__traceback__
        while tb is not None:
            module = str(tb.tb_frame.f_globals.get("__name__", ""))
            if module.split(".", maxsplit=1)[0] == "hushscript":
                for name, value in tb.tb_frame.f_locals.items():
                    yield module, f"{tb.tb_frame.f_code.co_name}.{name}", value
            tb = tb.tb_next
        pending.extend(part for part in (current.__cause__, current.__context__) if part)


def holds_text(value: object, secret: str, depth: int = 0) -> bool:
    """Whether `value` is, or is a plain container of, text that carries `secret`."""
    if depth > 6:  # a frame local nests a few levels at most
        return False
    if isinstance(value, str):
        return secret in value
    if isinstance(value, bytes):
        return secret.encode() in value
    if isinstance(value, dict):
        return any(holds_text(part, secret, depth + 1) for item in value.items() for part in item)
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(holds_text(part, secret, depth + 1) for part in value)
    return False


def assert_no_plain_secret(error: BaseException, *secrets: str) -> None:
    walked = list(sdk_locals(error))
    assert walked
    for module, where, value in walked:
        for secret in secrets:
            assert not holds_text(value, secret), f"{secret!r} is a plain local: {module} {where}"


def signed_url_of(api: FakeApi) -> str:
    return str(next(r for r in api.requests if r.method == "PUT" and "__r2" in r.url.path).url)


def no_etag(_n: int, _attempt: int) -> httpx.Response:
    return httpx.Response(200)


def test_a_failure_while_putting_a_part_leaves_the_signed_url_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=no_etag)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    url = signed_url_of(api)
    assert "sig=" in url
    assert_no_plain_secret(raised.value, url, url.split("?")[1])


@pytest.mark.anyio
async def test_the_asyncio_upload_leaves_the_signed_url_out_of_sdk_frames_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=no_etag)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    url = signed_url_of(api)
    assert_no_plain_secret(raised.value, url, url.split("?")[1])


def test_a_claim_answer_the_sdk_cannot_use_leaves_the_token_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = Routes(
        lambda _r: reply(201, {"pat": PAT, "user_id": 7, "scopes": [], "balance_seconds": 0})
    )
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    with pytest.raises(OutcomeUnknownError) as raised:
        Hushscript.agent_claim("sg_1", "s", base_url=BASE_URL, clock=FakeClock())
    assert raised.value.received_token == PAT
    assert_no_plain_secret(raised.value, PAT)


def test_a_failure_of_the_sdk_while_reading_a_claim_leaves_the_token_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(_token: Secret, _fields: dict[str, object]) -> AgentAccount:
        raise RuntimeError

    routes = Routes(
        lambda _r: reply(201, {"pat": PAT, "user_id": "u", "scopes": [], "balance_seconds": 0})
    )
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(agent_module, "account_of", refuse)
    with pytest.raises(OutcomeUnknownError) as raised:
        Hushscript.agent_claim("sg_1", "s", base_url=BASE_URL, clock=FakeClock())
    assert raised.value.received_token == PAT
    assert_no_plain_secret(raised.value, PAT)


def test_a_rotation_the_sdk_cannot_use_leaves_the_token_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _r: reply(200, {"pat": PAT, "pat_id": 7, "scopes": []}))
    with pytest.raises(OutcomeUnknownError) as raised:
        hs.agent.rotate_token()
    assert_no_plain_secret(raised.value, PAT)


def test_a_claim_that_fails_leaves_the_claim_secret_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    routes = Routes(refuse)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    with pytest.raises(NetworkError) as raised:
        Hushscript.agent_claim("sg_1", CLAIM_SECRET, base_url=BASE_URL, clock=FakeClock())
    assert json.loads(routes.requests[0].content) == {"claim_secret": CLAIM_SECRET}
    assert_no_plain_secret(raised.value, CLAIM_SECRET)


@pytest.mark.anyio
async def test_an_asyncio_claim_that_fails_leaves_the_claim_secret_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    routes = Routes(refuse)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
    with pytest.raises(NetworkError) as raised:
        await AsyncHushscript.agent_claim(
            "sg_1", CLAIM_SECRET, base_url=BASE_URL, clock=FakeClock()
        )
    assert_no_plain_secret(raised.value, CLAIM_SECRET)


def test_a_signup_answer_the_sdk_cannot_use_leaves_the_claim_secret_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {
        "signup_id": "sg_1",
        "claim_secret": CLAIM_SECRET,
        "checkout_url": "https://checkout.test/pay",
        "amount": 599,
        "currency": "USD",
        "expires_at": -1,
    }
    routes = Routes(lambda _r: reply(200, body))
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    with pytest.raises(HushscriptError) as raised:
        Hushscript.agent_signup(
            email="a@example.com",
            pack="45min",
            accept_terms="2026-10-01",
            agent=AgentInfo("a", "p"),
            base_url=BASE_URL,
            clock=FakeClock(),
        )
    assert raised.value.code == "bad_response"
    assert_no_plain_secret(raised.value, CLAIM_SECRET)
