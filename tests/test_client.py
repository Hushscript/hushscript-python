from __future__ import annotations

import httpx
import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import FakeClock, Script, error_body, reply
from hushscript import (
    AsyncHushscript,
    AuthenticationError,
    Balance,
    Hushscript,
    NetworkError,
    RateLimitError,
)
from hushscript._client import user_agent
from hushscript._errors import ApiError
from hushscript.generated.api.default import get_account


def _patch(monkeypatch: pytest.MonkeyPatch, script: Script) -> None:
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)


ACCOUNT = {
    "balance_seconds": 7260,
    "held_seconds": 30,
    "credits_expire_at": 1798859045,
    "card_on_file": False,
    "data_region": "eu",
    "limits": {
        "max_daily_seconds": 36000,
        "max_active_jobs": 50,
        "active_jobs": 0,
        "used_today_seconds": 0,
    },
    "purchases_remaining_in_window": 2,
}


def test_never_prints_token() -> None:
    hs = Hushscript(TOKEN)
    surface = repr(hs) + str(hs) + str(vars(hs)) + repr(hs.api) + str(vars(hs.api))
    assert TOKEN[12:] not in surface


def test_async_client_never_prints_token() -> None:
    hs = AsyncHushscript(TOKEN)
    assert TOKEN[12:] not in repr(hs) + str(vars(hs)) + repr(hs.api)


def test_the_token_is_not_stored_on_the_httpx_client() -> None:
    hs = Hushscript(TOKEN)
    assert "authorization" not in hs.api.get_httpx_client().headers
    assert hs.api.get_httpx_client().headers["User-Agent"] == user_agent()


def test_the_api_client_runs_on_the_same_retrying_httpx_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    clock = FakeClock()
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock)
    response = hs.api.get_httpx_client().get("/v1/account")
    assert response.status_code == 200
    assert script.calls == 2
    assert script.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"


def test_the_generated_operation_functions_use_the_hardened_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock())
    result = get_account.sync_detailed(client=hs.api)
    assert result.status_code == 200
    assert script.calls == 2


def test_user_agent_names_the_sdk_and_the_runtime() -> None:
    assert user_agent().startswith("hushscript-python/")
    assert " python/3." in user_agent()


def test_balance_reads_the_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010")
    balance = hs.balance()
    assert isinstance(balance, Balance)
    assert (balance.seconds, balance.minutes, balance.held_seconds) == (7260, 121, 30)
    assert balance.expires_at is not None
    assert balance.expires_at.year == 2027
    assert balance.purchases_remaining == 2


def test_balance_with_debt_truncates_toward_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"balance_seconds": -90, "held_seconds": 0, "credits_expire_at": None}
    _patch(monkeypatch, Script([reply(200, body)]))
    balance = Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()
    assert (balance.minutes, balance.expires_at, balance.purchases_remaining) == (-1, None, None)


@pytest.mark.parametrize(
    "body", [[], {"balance_seconds": "x", "held_seconds": 0}, {"balance_seconds": 1}]
)
def test_balance_rejects_an_unexpected_shape(monkeypatch: pytest.MonkeyPatch, body: object) -> None:
    _patch(monkeypatch, Script([reply(200, body)]))
    with pytest.raises(ApiError, match="account response"):
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()


def test_a_401_that_echoes_the_token_raises_a_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    body = error_body("unauthorized", 2000, details=f"bad token {TOKEN}")
    _patch(monkeypatch, Script([reply(401, body)]))
    with pytest.raises(AuthenticationError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()
    error = raised.value
    assert TOKEN[12:] not in " ".join(
        [str(error), repr(error), error.hint or "", repr(error.details)]
    )


def test_retry_after_61_raises_at_once_without_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch, Script([reply(429, error_body("rate_limited", 5000), {"Retry-After": "61"})])
    )
    clock = FakeClock()
    with pytest.raises(RateLimitError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock).balance()
    assert raised.value.retry_after == 61
    assert clock.sleeps == []


def test_context_manager_closes_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    with Hushscript(TOKEN, base_url="http://127.0.0.1:4010") as hs:
        hs.balance()
    with pytest.raises(RuntimeError, match="closed"):
        hs.balance()


def test_a_dead_network_surfaces_as_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([httpx.ConnectError("refused")]))
    with pytest.raises(NetworkError):
        Hushscript(
            TOKEN, base_url="http://127.0.0.1:4010", max_retries=1, clock=FakeClock()
        ).balance()


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUSHSCRIPT_TOKEN", TOKEN)
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://127.0.0.1:4010")
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    assert Hushscript().balance().seconds == 7260


@pytest.mark.anyio
async def test_async_balance_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(503), reply(200, ACCOUNT)]))
    async with AsyncHushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock()) as hs:
        assert (await hs.balance()).minutes == 121
    _patch(monkeypatch, Script([reply(401, error_body("unauthorized", 2000))]))
    async with AsyncHushscript(TOKEN, base_url="http://127.0.0.1:4010") as hs:
        with pytest.raises(AuthenticationError):
            await hs.balance()
