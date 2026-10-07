"""The two examples that move money or tokens: what they print, and how they keep a token."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import error_body, reply
from hushscript import HushscriptError, OutcomeUnknownError, PaymentMethodRequiredError
from routes import Routes

if TYPE_CHECKING:
    from types import ModuleType

    import httpx

EXAMPLES = Path(__file__).parent.parent / "examples"
NEW_TOKEN = "hsr1:eu:pat." + "ab" * 16 + "." + "cd" * 32
SECOND_TOKEN = "hsr1:eu:pat." + "ef" * 16 + "." + "01" * 32


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


buy = load("buy")
agent_signup = load("agent_signup")


def sent_error(status: int | None, key: str | None) -> HushscriptError:
    error = HushscriptError("failed", code="x", status=status)
    error.idempotency_key = key
    return error


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422, 429])
def test_a_refusal_says_nothing_was_charged(
    status: int, capsys: pytest.CaptureFixture[str]
) -> None:
    buy.report(sent_error(status, "key-1"))
    err = capsys.readouterr().err
    assert "Nothing was charged." in err
    assert "may have been charged" not in err
    assert "--key" not in err


@pytest.mark.parametrize("status", [None, 408, 409, 500, 502, 503, 200, 201])
def test_any_other_outcome_after_the_send_says_it_may_have_been_charged(
    status: int | None, capsys: pytest.CaptureFixture[str]
) -> None:
    buy.report(sent_error(status, "key-1"))
    err = capsys.readouterr().err
    assert "The card may have been charged." in err
    assert "--key key-1" in err
    assert "Nothing was charged." not in err


def test_an_error_before_the_send_charged_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    buy.report(PaymentMethodRequiredError("no card"))
    err = capsys.readouterr().err
    assert "Nothing was charged." in err
    assert "--key" not in err


def test_a_key_flag_without_a_value_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["buy.py", "300min", "--yes", "--key"])
    with pytest.raises(SystemExit) as exited:
        buy.parser().parse_args()
    assert exited.value.code == 2
    assert "expected one argument" in capsys.readouterr().err


PACK = {
    "id": "300min",
    "amount": 599,
    "currency": "USD",
    "seconds": 18000,
    "referral_bonus_seconds": 0,
}


def shop(monkeypatch: pytest.MonkeyPatch) -> Routes:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/billing/packs":
            return reply(200, {"packs": [PACK]})
        if path == "/v1/billing/cards":
            method = {
                "id": "pm_1",
                "type": "card",
                "brand": "visa",
                "last4": "4242",
                "exp_month": 1,
                "exp_year": 2030,
                "is_default": True,
                "fast_checkout_eligible": True,
            }
            return reply(200, {"default_id": "pm_1", "methods": [method]})
        return reply(200, {"status": "ok", "balance_seconds": 18000})

    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setenv("HUSHSCRIPT_TOKEN", TOKEN)
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://127.0.0.1:4010")
    return routes


def purchases(routes: Routes) -> list[dict[str, object]]:
    return [json.loads(r.content) for r in routes.requests if r.url.path.endswith("/purchase")]


def test_without_yes_nothing_is_bought(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    routes = shop(monkeypatch)
    assert buy.main("300min", yes=False, key=None) == 1
    assert purchases(routes) == []
    assert "Nothing was bought." in capsys.readouterr().out


def test_a_pack_that_is_not_listed_buys_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = shop(monkeypatch)
    assert buy.main("nope", yes=True, key=None) == 2
    assert purchases(routes) == []


def test_with_yes_the_pack_is_bought_with_the_notice_acknowledged_and_the_given_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    routes = shop(monkeypatch)
    assert buy.main("300min", yes=True, key="retry-key-1") == 0
    [purchase] = purchases(routes)
    assert purchase["policy_ack"] is True
    assert purchase["idempotency_key"] == "retry-key-1"
    assert "now 300 minutes" in capsys.readouterr().out


# --- the agent example's token file ---


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_a_token_is_kept_with_mode_0600_and_replaces_an_older_one(tmp_path: Path) -> None:
    path = tmp_path / "agent-token"
    path.write_text("old\n")
    path.chmod(0o644)
    agent_signup.keep(path, NEW_TOKEN)
    assert path.read_text() == f"{NEW_TOKEN}\n"
    assert mode(path) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["agent-token"]


def test_the_old_token_survives_a_write_that_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "agent-token"
    path.write_text("old-token\n")

    def broken(_descriptor: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", broken)
    with pytest.raises(OSError, match="disk full"):
        agent_signup.keep(path, NEW_TOKEN)
    assert path.read_text() == "old-token\n"
    assert [p.name for p in tmp_path.iterdir()] == ["agent-token"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (NEW_TOKEN, True),
        ("hsr", True),
        (None, False),
        ("", False),
        ("abc", False),
        ("hsr1 x", False),
        ("hsr1é", False),
        ("hsr1\n", False),
    ],
)
def test_only_a_token_shaped_text_is_kept_from_a_failed_answer(
    text: str | None,
    expected: bool,  # noqa: FBT001
) -> None:
    assert agent_signup.looks_like_token(text) is expected


SIGNUP = {
    "signup_id": "sg_1",
    "claim_secret": "cs",
    "checkout_url": "https://checkout.test/pay",
    "pack": "45min",
    "amount": 599,
    "currency": "USD",
    "expires_at": 1_700_001_800,
}


def no_sleep(_seconds: float) -> None:
    return None


def agent_api(
    monkeypatch: pytest.MonkeyPatch, claims: list[httpx.Response], rotate: httpx.Response
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/agent/accounts":
            return reply(201, SIGNUP)
        if path.endswith("/claim"):
            return claims.pop(0)
        if path == "/v1/agent/credentials/rotate":
            return rotate
        return reply(200, {"balance_seconds": 2700, "held_seconds": 0})

    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(agent_signup.time, "sleep", no_sleep)
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://127.0.0.1:4010")


CLAIMED = {"user_id": "u_1", "pat": NEW_TOKEN, "scopes": ["transcribe"], "balance_seconds": 2700}
ROTATED = {"pat": SECOND_TOKEN, "pat_id": "pat_2", "scopes": ["transcribe"]}


def test_the_agent_flow_keeps_the_claimed_token_and_then_the_rotated_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent_api(
        monkeypatch,
        [reply(409, error_body("wrong_state", 4001)), reply(201, CLAIMED)],
        reply(201, ROTATED),
    )
    path = tmp_path / "agent-token"
    agent_signup.run("2026-10-01", path, [])
    assert path.read_text() == f"{SECOND_TOKEN}\n"
    assert mode(path) == 0o600
    assert "claimed u_1" in capsys.readouterr().out


def test_a_failed_rotation_leaves_the_claimed_token_in_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_api(monkeypatch, [reply(201, CLAIMED)], reply(401, error_body("unauthorized", 2000)))
    path = tmp_path / "agent-token"
    kept: list[Path] = []
    with pytest.raises(HushscriptError):
        agent_signup.run("2026-10-01", path, kept)
    assert path.read_text() == f"{NEW_TOKEN}\n"
    assert kept == [path]


def test_a_token_that_came_with_an_unusable_answer_is_kept_only_when_it_passes_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "agent-token"
    path.write_text("earlier\n")
    bad = {**CLAIMED, "pat": "not-a-token", "user_id": 5}
    agent_api(monkeypatch, [reply(201, bad)], reply(201, ROTATED))
    monkeypatch.setattr(sys, "argv", ["x", "--terms", "t", "--token-file", str(path)])
    assert agent_signup.main() == 1
    assert path.read_text() == "earlier\n"
    good_token_bad_user = {**CLAIMED, "user_id": 5}
    agent_api(monkeypatch, [reply(201, good_token_bad_user)], reply(201, ROTATED))
    assert agent_signup.main() == 1
    assert path.read_text() == f"{NEW_TOKEN}\n"
    assert mode(path) == 0o600
    assert isinstance(OutcomeUnknownError("x"), HushscriptError)
    err = capsys.readouterr().err
    assert "A token that came with the failed answer" in err
    assert "Any token that was issued" not in err


def test_a_token_with_padding_in_a_failed_answer_is_saved_trimmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "agent-token"
    padded = {**CLAIMED, "pat": f"  {NEW_TOKEN}\n", "user_id": 5}
    agent_api(monkeypatch, [reply(201, padded)], reply(201, ROTATED))
    monkeypatch.setattr(sys, "argv", ["x", "--terms", "t", "--token-file", str(path)])
    assert agent_signup.main() == 1
    assert path.read_text() == f"{NEW_TOKEN}\n"


def test_a_signup_that_failed_before_any_token_does_not_claim_one_was_issued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    routes = Routes(lambda _request: reply(422, error_body("bad_request", 1000)))
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://127.0.0.1:4010")
    path = tmp_path / "agent-token"
    monkeypatch.setattr(sys, "argv", ["x", "--terms", "t", "--token-file", str(path)])
    assert agent_signup.main() == 1
    err = capsys.readouterr().err
    assert "Any token that was issued" not in err
    assert not path.exists()


def test_a_failure_after_a_saved_token_says_where_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent_api(monkeypatch, [reply(201, CLAIMED)], reply(401, error_body("unauthorized", 2000)))
    path = tmp_path / "agent-token"
    monkeypatch.setattr(sys, "argv", ["x", "--terms", "t", "--token-file", str(path)])
    assert agent_signup.main() == 1
    assert f"Any token that was issued is in {path}." in capsys.readouterr().err


def test_the_readme_retry_snippet_refuses_what_the_buy_example_refuses() -> None:
    readme = (EXAMPLES.parent / "README.md").read_text(encoding="utf-8")
    match = re.search(r"refused = error\.status in \{([^}]*)\}", readme)
    assert match is not None
    assert {int(code) for code in match.group(1).split(",")} == set(buy.REFUSALS)
