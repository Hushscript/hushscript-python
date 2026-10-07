"""Nothing the client holds or hands out shows a token, a received token or a signed URL."""

from __future__ import annotations

import copy
import dataclasses
import logging
import pickle
import pprint
from typing import Any

import httpx
import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import BASE_URL, FakeClock, reply
from hushscript import (
    AgentAccount,
    Balance,
    Hushscript,
    OutcomeUnknownError,
    Purchase,
    RotatedToken,
)
from hushscript._redact import REDACTED, Credentials, Secret
from hushscript.transcribe.upload import Created, parse_created
from routes import Routes, hs_on

ODD = "hsr1-oddé-RECEIVED-SECRET"
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
    for result in (
        Purchase(60, 1),
        Balance(1, 0, 0, None, None),
        AgentAccount("tok", "u", ["a"], Balance(1, 0, 0, None, None)),
        RotatedToken("tok", "id", ["a"], None),
    ):
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
