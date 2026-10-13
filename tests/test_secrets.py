"""Nothing the client holds or hands out shows a token, a received token or a signed URL."""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
import pickle
import pprint
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

import hushscript._client as client_module
import hushscript.resources.agent as agent_module
from conftest import TOKEN
from fakeapi import FakeApi
from helpers import (
    BASE_URL,
    FakeClock,
    Script,
    async_client,
    reply,
    settings_for,
    snapshot,
    stand_in,
    sync_client,
)
from hushscript import (
    AgentAccount,
    AgentInfo,
    AgentSignup,
    ApiError,
    AsyncHushscript,
    Balance,
    Hushscript,
    HushscriptError,
    NetworkError,
    OutcomeUnknownError,
    Purchase,
    RotatedToken,
    UploadError,
    ValidationError,
)
from hushscript._http import _Attempt  # pyright: ignore[reportPrivateUsage]
from hushscript._redact import REDACTED, Credentials, Secret
from hushscript.generated.api.default import get_account
from hushscript.money import to_money
from hushscript.transcribe.upload import Created, parse_created
from pipe import async_hs_for, hs_for, media
from routes import Routes, async_hs_on, hs_on

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Iterator
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
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/billing/cards":
            return reply(200, {"default_id": "pm_1", "methods": []})
        assert request.url.path == "/v1/billing/purchase"
        return reply(400, {"error": "bad_request", "code": 1, "details": {"echo": TOKEN}})

    hs, routes = hs_on(monkeypatch, handler)
    with pytest.raises(ValidationError) as raised:
        hs.buy("300min", idempotency_key="redaction_key")
    assert (raised.value.code, raised.value.status) == ("bad_request", 400)
    assert [request.url.path for request in routes.requests] == [
        "/v1/billing/cards",
        "/v1/billing/purchase",
    ]
    assert (
        raised.value.idempotency_key
        == json.loads(routes.requests[-1].content)["idempotency_key"]
        == "redaction_key"
    )
    texts = [str(raised.value), repr(raised.value), repr(raised.value.details)]
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
                datetime.fromtimestamp(1_700_001_800, tz=timezone.utc),
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


@pytest.mark.parametrize(("result", "secret"), with_secrets())
def test_agent_result_representations_hide_unknown_fields_echoing_credentials(
    result: Any, secret: str
) -> None:
    result = dataclasses.replace(result, _extra={"echo": {"credential": secret}})
    for text in (repr(result), str(result), pprint.pformat(result), repr([result])):
        assert secret not in text
        assert "_extra" not in text
        assert "[redacted]" in text
    assert result.extra["echo"] == {"credential": secret}
    assert dataclasses.asdict(result)["_extra"]["echo"]["credential"] == secret


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


def _request_parts(request: httpx.Request) -> list[object]:
    try:
        content = request.content
    except httpx.RequestNotRead:
        content = b""
    return [request.url, request.headers, content, request.stream, request.extensions]


def _attributes(value: object) -> list[object]:
    """Every attribute of an object: its `__dict__` and its slots."""
    held: list[object] = [getattr(value, "__dict__", {})]
    for cls in type(value).__mro__:
        slots = getattr(cls, "__slots__", ())
        names = (slots,) if isinstance(slots, str) else slots
        held.extend(
            getattr(value, name, None) for name in names if name not in {"__dict__", "__weakref__"}
        )
    return held


_WALKED_PACKAGES = frozenset({"hushscript", "httpx", "httpcore"})
"""The SDK's objects and the HTTP library's responses (request, stream, read body) and stream
wrappers, walked through their attributes."""


def _walked(value: object) -> bool:
    return (
        not isinstance(value, type)
        and type(value).__module__.split(".", maxsplit=1)[0] in _WALKED_PACKAGES
    )


def _error_parts(error: BaseException) -> list[object]:
    return [error.__cause__, error.__context__, *error.args, *_attributes(error)]


def _header_parts(headers: httpx.Headers) -> list[object]:
    return [headers.raw]


_PARTS: tuple[tuple[type[Any], Callable[[Any], list[object]]], ...] = (
    (BaseException, _error_parts),
    (httpx.Request, _request_parts),
    (httpx.Headers, _header_parts),
)


def _children(value: object) -> list[object]:
    for kind, parts in _PARTS:
        if isinstance(value, kind):
            return parts(value)
    if isinstance(value, dict):
        pairs = cast("dict[object, object]", value)
        return [*pairs.keys(), *pairs.values()]
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(cast("Iterable[object]", value))
    return _attributes(value) if _walked(value) else []


def holds_text(value: object, secret: str, seen: set[int] | None = None) -> bool:
    """Whether `value` is, or reaches through SDK objects, exceptions (cause, context, arguments,
    attributes), containers and the HTTP library's requests, responses and streams, plain secret
    text. `Secret` and `Credentials` are the two designated holders at rest and are
    not entered."""
    if type(value) in {Secret, Credentials}:
        return False
    if isinstance(value, bytes):
        return secret.encode() in value
    if isinstance(value, (str, httpx.URL)):
        return secret in str(value)
    visited: set[int] = set() if seen is None else seen
    if id(value) in visited:
        return False
    visited.add(id(value))
    return any(holds_text(child, secret, visited) for child in _children(value))


def context_of(original: Exception) -> HushscriptError:
    """An SDK error raised while `original` was being handled."""
    error = HushscriptError("wrapped")
    error.__context__ = original
    return error


def cause_of(original: Exception) -> HushscriptError:
    error = HushscriptError("wrapped")
    error.__cause__ = original
    return error


@pytest.mark.parametrize(
    ("value", "secret", "expected"),
    [
        pytest.param(httpx.URL(SIGNED), "SIGNED-SECRET", True, id="url"),
        pytest.param(httpx.Request("PUT", SIGNED), "SIGNED-SECRET", True, id="request-url"),
        pytest.param(
            httpx.Request("GET", BASE_URL, headers={"Authorization": f"Bearer {PAT}"}),
            PAT,
            True,
            id="request-header",
        ),
        pytest.param(
            httpx.Request("POST", BASE_URL, json={"claim_secret": CLAIM_SECRET}),
            CLAIM_SECRET,
            True,
            id="request-body",
        ),
        pytest.param(httpx.Headers({"Authorization": f"Bearer {PAT}"}), PAT, True, id="headers"),
        pytest.param(Secret(SIGNED), "SIGNED-SECRET", False, id="secret-holder"),
        pytest.param(
            httpx.Response(200, request=httpx.Request("PUT", SIGNED)),
            "SIGNED-SECRET",
            True,
            id="response-request",
        ),
        pytest.param(
            httpx.Response(200, content=CLAIM_SECRET.encode()),
            CLAIM_SECRET,
            True,
            id="response-body",
        ),
        pytest.param(
            httpx.Response(200, stream=httpx.ByteStream(PAT.encode())),
            PAT,
            True,
            id="response-stream",
        ),
        pytest.param(
            httpx.ReadError("reset", request=httpx.Request("PUT", SIGNED)),
            "SIGNED-SECRET",
            True,
            id="error-request",
        ),
        pytest.param(context_of(ValueError(SIGNED)), "SIGNED-SECRET", True, id="error-context"),
        pytest.param(cause_of(ValueError(SIGNED)), "SIGNED-SECRET", True, id="error-cause"),
        pytest.param(
            json.JSONDecodeError("Expecting ','", f'{{"claim_secret": "{CLAIM_SECRET}"', 30),
            CLAIM_SECRET,
            True,
            id="json-error-doc",
        ),
        pytest.param(
            httpx.Response(200, request=httpx.Request("GET", BASE_URL)),
            "SIGNED-SECRET",
            False,
            id="clean-response",
        ),
    ],
)
def test_the_frame_probe_detects_plain_http_secrets(
    value: object,
    secret: str,
    expected: bool,  # noqa: FBT001  # detector expectation
) -> None:
    assert holds_text(value, secret) is expected


@pytest.mark.parametrize("secret", [PAT, SIGNED, CLAIM_SECRET])
def test_the_frame_probe_detects_secrets_in_sdk_object_attributes(
    secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = settings_for(FakeClock())
    settings.base_url = httpx.URL(secret if secret == SIGNED else BASE_URL)
    attempt = _Attempt(httpx.Request("POST", BASE_URL), settings)
    monkeypatch.setattr(attempt, "plain_control", {"nested": [(secret,)]}, raising=False)
    monkeypatch.setattr(attempt, "cycle", attempt, raising=False)
    assert holds_text(attempt, secret) is True
    monkeypatch.delattr(attempt, "plain_control")
    assert holds_text(attempt, secret) is (secret == SIGNED)


@pytest.mark.parametrize(
    ("method", "url", "body", "kept"),
    [
        pytest.param(
            "POST",
            f"{BASE_URL}/v1/agent/accounts/sg_1/claim?x=1",
            {"claim_secret": CLAIM_SECRET},
            f"{BASE_URL}/v1/agent/accounts/sg_1/claim",
            id="claim",
        ),
        pytest.param("PUT", SIGNED, None, "https://acct.r2.example.com/b/part-1", id="signed-part"),
    ],
)
def test_an_attempt_holds_its_secrets_until_it_finishes_and_then_strips_the_request(
    method: str, url: str, body: dict[str, object] | None, kept: str
) -> None:
    request = httpx.Request(method, url, json=body) if body else httpx.Request(method, url)
    attempt = _Attempt(request, settings_for(FakeClock(), token=PAT))
    attempt.begin()
    secrets = (PAT, CLAIM_SECRET) if body else ("SIGNED-SECRET",)
    for secret in secrets:
        assert holds_text(attempt, secret) is True
        assert holds_text(request, secret) is True
    attempt.finish()
    attempt.finish()  # a second end is a no-op
    for secret in secrets:
        assert holds_text(attempt, secret) is False
        assert holds_text(request, secret) is False
    assert (request.method, str(request.url)) == (method, kept)
    assert "Authorization" not in request.headers
    assert request.content == b""


def assert_no_plain_secret(error: BaseException, *secrets: str) -> None:
    walked = list(sdk_locals(error))
    assert len(walked) > 0
    for module, where, value in walked:
        for secret in secrets:
            assert holds_text(value, secret) is False, (
                f"{secret!r} is a plain local: {module} {where}"
            )


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
    assert (raised.value.code, raised.value.status) == ("etag_missing", None)
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
    assert (raised.value.code, raised.value.status) == ("etag_missing", None)
    url = signed_url_of(api)
    assert_no_plain_secret(raised.value, url, url.split("?")[1])


class Streamed(httpx.SyncByteStream, httpx.AsyncByteStream):
    """A body that arrives as a stream, unlike FakeApi's read ones, so the SDK's own end-of-body
    path runs; it notes being closed."""

    def __init__(self) -> None:
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield b"ok"

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"ok"

    def close(self) -> None:
        self.closed = True

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_a_streamed_part_answer_is_closed_and_leaves_the_signed_url_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    bodies: list[Streamed] = []

    def streamed_without_etag(_n: int, _attempt: int) -> httpx.Response:
        bodies.append(Streamed())
        return httpx.Response(200, stream=bodies[-1])

    api = FakeApi(r2_hook=streamed_without_etag)
    if asynchronous:
        hs = async_hs_for(monkeypatch, api)
        with pytest.raises(UploadError) as raised:
            await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    else:
        with pytest.raises(UploadError) as raised:
            hs_for(monkeypatch, api).transcribe(media(), duration_seconds=100, concurrency=1)
    assert (raised.value.code, raised.value.status) == ("etag_missing", None)
    assert [body.closed for body in bodies] == [True]
    url = signed_url_of(api)
    assert_no_plain_secret(raised.value, url, url.split("?")[1])


def unreachable(_n: int, _attempt: int) -> httpx.Response:
    raise httpx.ConnectError("refused")


def test_a_network_failure_while_putting_a_part_leaves_the_signed_url_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=unreachable, part_hook=unreachable)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(NetworkError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert (raised.value.code, raised.value.status) == ("network_error", None)
    url = signed_url_of(api)
    assert_no_plain_secret(raised.value, url, url.split("?")[1], TOKEN)


@pytest.mark.anyio
async def test_the_asyncio_network_failure_on_a_part_leaves_the_signed_url_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=unreachable, part_hook=unreachable)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(NetworkError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert (raised.value.code, raised.value.status) == ("network_error", None)
    url = signed_url_of(api)
    assert_no_plain_secret(raised.value, url, url.split("?")[1], TOKEN)


def refuse_part(_n: int, _attempt: int) -> httpx.Response:
    return reply(400, {"error": "bad_request", "code": 1000})


def test_a_proxied_part_failure_leaves_the_token_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(proxied=True, part_hook=refuse_part)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ValidationError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert (raised.value.code, raised.value.status) == ("bad_request", 400)
    parts = api.of("PUT", r"/v1/uploads/[^/]+/parts/[^/]+")
    assert len(parts) == 1
    assert parts[0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert_no_plain_secret(raised.value, TOKEN)


@pytest.mark.anyio
async def test_an_asyncio_proxied_part_failure_leaves_the_token_out_of_sdk_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(proxied=True, part_hook=refuse_part)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(ValidationError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert (raised.value.code, raised.value.status) == ("bad_request", 400)
    parts = api.of("PUT", r"/v1/uploads/[^/]+/parts/[^/]+")
    assert len(parts) == 1
    assert parts[0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert_no_plain_secret(raised.value, TOKEN)


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
    assert raised.value.message == (
        "The answer to POST /v1/agent/accounts/{signup_id}/claim could not be used (RuntimeError), "
        "so the token may be lost."
    )
    assert stand_in(raised.value) == "RuntimeError"
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
    assert (raised.value.code, raised.value.status) == ("network_error", None)
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
    assert (raised.value.code, raised.value.status) == ("network_error", None)
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


def frames_of(traceback: TracebackType | None) -> list[tuple[str, dict[str, object]]]:
    """The code name and the locals of every frame on `traceback`, whoever's frame it is."""
    frames: list[tuple[str, dict[str, object]]] = []
    while traceback is not None:
        frames.append((traceback.tb_frame.f_code.co_name, dict(traceback.tb_frame.f_locals)))
        traceback = traceback.tb_next
    return frames


class Refusal(Script):
    """Fails the way httpx does: the error keeps the request it was sending."""

    def _next(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(snapshot(request))
        raise httpx.ReadError("reset", request=request)


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("path", "error_class"),
    [
        ("/v1/account", NetworkError),
        ("/v1/agent/accounts/sg_1/claim", OutcomeUnknownError),
    ],
)
async def test_a_transport_failure_carries_a_stand_in_whose_frames_hold_no_request(
    asynchronous: bool,  # noqa: FBT001
    path: str,
    error_class: type[HushscriptError],
) -> None:
    script = Refusal([httpx.Response(200)])
    if asynchronous:
        async with async_client(script, FakeClock(), token=PAT, max_retries=0) as client:
            with pytest.raises(error_class) as raised:
                await client.post(path, json={"claim_secret": CLAIM_SECRET})
    else:
        with (
            sync_client(script, FakeClock(), token=PAT, max_retries=0) as client,
            pytest.raises(error_class) as raised,
        ):
            client.post(path, json={"claim_secret": CLAIM_SECRET})
    assert script.requests[0].headers["Authorization"] == f"Bearer {PAT}"
    assert json.loads(script.requests[0].content) == {"claim_secret": CLAIM_SECRET}
    assert stand_in(raised.value) == "ReadError: reset"
    cause = raised.value.__cause__
    assert cause is not None
    frames = frames_of(cause.__traceback__)
    assert [held for code, held in frames if code == "_next"] == [{}]
    for code, held in frames:
        for name, value in held.items():
            for secret in (PAT, CLAIM_SECRET):
                assert holds_text(value, secret) is False, f"{secret!r} in {code}.{name}"


def test_a_body_that_is_not_json_carries_a_stand_in_without_the_body() -> None:
    truncated = b'{"signup_id": "sg_1", "claim_secret": "' + CLAIM_SECRET.encode()
    routes = Routes(lambda _r: httpx.Response(200, content=truncated))
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
        with pytest.raises(ApiError) as raised:
            Hushscript.agent_signup(
                email="a@example.com",
                pack="45min",
                accept_terms="2026-10-01",
                agent=AgentInfo("a", "p"),
                base_url=BASE_URL,
                clock=FakeClock(),
            )
    described = "JSONDecodeError: Unterminated string starting at: line 1 column 39 (char 38)"
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert raised.value.message == f"The API's response could not be used ({described})."
    assert stand_in(raised.value) == described
    assert vars(raised.value.__cause__) == {}


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_a_claim_secret_echoed_by_a_failure_or_an_answer_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused {CLAIM_SECRET}", request=request)

    def echo(_request: httpx.Request) -> httpx.Response:
        return reply(
            401, {"error": "agent_claim_invalid", "code": 3005, "details": {"seen": CLAIM_SECRET}}
        )

    async def claim() -> None:
        if asynchronous:
            await AsyncHushscript.agent_claim(
                "sg_1", CLAIM_SECRET, base_url=BASE_URL, clock=FakeClock()
            )
        else:
            Hushscript.agent_claim("sg_1", CLAIM_SECRET, base_url=BASE_URL, clock=FakeClock())

    errors: list[HushscriptError] = []
    for handler, kind in ((refuse, NetworkError), (echo, HushscriptError)):
        routes = Routes(handler)
        monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
        monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
        with pytest.raises(kind) as raised:
            await claim()
        errors.append(raised.value)
    lost, refused = errors
    assert lost.message == (
        "Could not reach the Hushscript API: POST /v1/agent/accounts/sg_1/claim "
        f"(ConnectError: refused {REDACTED})."
    )
    assert stand_in(lost) == f"ConnectError: refused {REDACTED}"
    assert (refused.code, refused.status) == ("agent_claim_invalid", 401)
    assert refused.details == {"seen": REDACTED}


@pytest.mark.parametrize(("length", "scrubbed"), [(15, False), (16, True)])
def test_a_claim_secret_is_registered_from_the_length_of_a_token_secret_part(
    length: int,
    scrubbed: bool,  # noqa: FBT001
) -> None:
    secret = "c" * length
    credentials = Credentials()
    agent_module.remember_claim_secret(credentials, Secret(secret))
    assert credentials.scrub(f"echo {secret}") == (
        f"echo {REDACTED}" if scrubbed else f"echo {secret}"
    )


@pytest.mark.parametrize("status", [400, 401, 500])
@pytest.mark.parametrize("malformed", [False, True])
def test_error_answer_echoes_leave_no_plain_secret_in_sdk_objects(
    monkeypatch: pytest.MonkeyPatch, status: int, *, malformed: bool
) -> None:
    text = json.dumps({"error": "bad_request", "code": 1000, "echo": TOKEN, "url": SIGNED})
    if malformed:
        text += " broken"
    hs, _ = hs_on(monkeypatch, lambda _r: httpx.Response(status, text=text))
    with pytest.raises(ApiError) as raised:
        hs.balance()
    assert_no_plain_secret(raised.value, TOKEN, "SIGNED-SECRET")
    assert raised.value.status == status
    if not malformed:
        assert raised.value.details["echo"] == REDACTED
        assert str(raised.value.details["url"]).endswith("?[redacted]")


@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 401, 500])
@pytest.mark.parametrize("malformed", [False, True])
async def test_async_error_answer_echoes_leave_no_plain_secret_in_sdk_objects(
    monkeypatch: pytest.MonkeyPatch, status: int, *, malformed: bool
) -> None:
    text = json.dumps({"error": "bad_request", "code": 1000, "echo": TOKEN, "url": SIGNED})
    if malformed:
        text += " broken"
    hs, _ = async_hs_on(monkeypatch, lambda _r: httpx.Response(status, text=text))
    with pytest.raises(ApiError) as raised:
        await hs.balance()
    assert_no_plain_secret(raised.value, TOKEN, "SIGNED-SECRET")
    assert raised.value.status == status


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("shape", ["object", "list", "string"])
@pytest.mark.parametrize("surface", ["friendly", "generated"])
async def test_unusable_success_shapes_leave_no_plain_secrets_in_sdk_frames(
    monkeypatch: pytest.MonkeyPatch, shape: str, surface: str, *, asynchronous: bool
) -> None:
    echo = {"echo": TOKEN, "url": SIGNED, "claim_secret": CLAIM_SECRET}
    body: object = echo if shape == "object" else [echo] if shape == "list" else json.dumps(echo)
    if asynchronous:
        async_hs, _ = async_hs_on(monkeypatch, lambda _r: reply(200, body))
        with pytest.raises(ApiError) as raised:
            await (
                get_account.asyncio(client=async_hs.api)
                if surface == "generated"
                else async_hs.balance()
            )
    else:
        hs, _ = hs_on(monkeypatch, lambda _r: reply(200, body))
        with pytest.raises(ApiError) as raised:
            get_account.sync(client=hs.api) if surface == "generated" else hs.balance()
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert stand_in(raised.value)
    assert raised.value.__context__ is None
    assert_no_plain_secret(raised.value, TOKEN, "SIGNED-SECRET", CLAIM_SECRET)


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["signup", "claim", "rotate"])
async def test_unusable_credential_successes_leave_no_plain_secrets_in_sdk_frames(
    monkeypatch: pytest.MonkeyPatch, operation: str, *, asynchronous: bool
) -> None:
    body = {"pat": PAT, "claim_secret": CLAIM_SECRET, "echo": TOKEN, "url": SIGNED}
    routes = Routes(lambda _r: reply(201, body))
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)

    async def invoke() -> None:
        if operation == "signup":
            if asynchronous:
                await AsyncHushscript.agent_signup(
                    email="a@example.com",
                    pack="45min",
                    accept_terms="2026-10-01",
                    agent=AgentInfo("a", "p"),
                    base_url=BASE_URL,
                )
            else:
                Hushscript.agent_signup(
                    email="a@example.com",
                    pack="45min",
                    accept_terms="2026-10-01",
                    agent=AgentInfo("a", "p"),
                    base_url=BASE_URL,
                )
        elif operation == "claim":
            if asynchronous:
                await AsyncHushscript.agent_claim("sg_1", CLAIM_SECRET, base_url=BASE_URL)
            else:
                Hushscript.agent_claim("sg_1", CLAIM_SECRET, base_url=BASE_URL)
        elif asynchronous:
            await AsyncHushscript(TOKEN, base_url=BASE_URL).agent.rotate_token()
        else:
            Hushscript(TOKEN, base_url=BASE_URL).agent.rotate_token()

    with pytest.raises(HushscriptError) as raised:
        await invoke()
    if operation == "signup":
        assert raised.value.code == "bad_response"
    else:
        assert isinstance(raised.value, OutcomeUnknownError)
        assert raised.value.received_token == PAT
    assert_no_plain_secret(raised.value, TOKEN, "SIGNED-SECRET", CLAIM_SECRET, PAT)
