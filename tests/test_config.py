from __future__ import annotations

import asyncio
from typing import Any

import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import Script, reply
from hushscript import AgentInfo, AsyncHushscript, ConfigurationError, Hushscript
from hushscript._config import resolve_config
from hushscript.generated.hints import HINTS


def test_refuses_construction_without_a_token_and_says_where_to_get_one() -> None:
    with pytest.raises(ConfigurationError, match="HUSHSCRIPT_TOKEN") as raised:
        Hushscript()
    assert raised.value.code == "config_invalid"
    assert raised.value.status is None
    assert raised.value.hint == (
        "Set HUSHSCRIPT_TOKEN or pass a token. Create one in the Hushscript app: "
        "Account → MCP (app.hushscript.com/account/mcp)."
    )


def test_missing_token_message_is_in_the_exception_text() -> None:
    with pytest.raises(ConfigurationError) as raised:
        resolve_config(None, env={})
    assert "No Hushscript token" in str(raised.value)


def test_a_token_without_the_hsr_prefix_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="doesn't look like a Hushscript token") as raised:
        resolve_config("sk-live-123", env={})
    assert "sk-live-123" not in str(raised.value)
    assert raised.value.hint is None


def test_the_token_comes_from_the_argument_before_the_environment() -> None:
    config = resolve_config(TOKEN, env={"HUSHSCRIPT_TOKEN": "hsr1:us:pat.aa.bb"})
    assert config.credentials.token == TOKEN


def test_the_token_comes_from_the_environment() -> None:
    config = resolve_config(None, env={"HUSHSCRIPT_TOKEN": f"  {TOKEN}\n"})
    assert config.credentials.token == TOKEN


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.example.com", "https://api.example.com"),
        ("https://api.example.com/", "https://api.example.com"),
        ("http://127.0.0.1:4010", "http://127.0.0.1:4010"),
        ("http://localhost:4010/", "http://localhost:4010"),
        ("http://[::1]:4010", "http://[::1]:4010"),
    ],
)
def test_accepted_base_urls(raw: str, expected: str) -> None:
    assert resolve_config(TOKEN, base_url=raw, env={}).base_url == expected


@pytest.mark.parametrize(
    "raw",
    [
        "http://api.example.com",
        "ftp://127.0.0.1",
        "https://",
        "https://user:pass@api.example.com",
        "api.example.com",
        "https://api.example.com/api",
        "https://api.example.com/v1/",
        "http://127.0.0.1:4010/mock",
        "https://api.example.com?x=1",
        "https://api.example.com/?",
        "https://api.example.com#top",
        "https://api.example.com/#",
    ],
)
def test_refused_base_urls(raw: str) -> None:
    with pytest.raises(ConfigurationError, match="base_url"):
        resolve_config(TOKEN, base_url=raw, env={})


def test_defaults_and_environment_overrides() -> None:
    config = resolve_config(TOKEN, env={})
    assert (config.base_url, config.timeout, config.max_retries, config.log_level) == (
        "https://api.hushscript.com",
        60.0,
        3,
        "off",
    )
    overridden = resolve_config(
        TOKEN, env={"HUSHSCRIPT_BASE_URL": "http://127.0.0.1:1", "HUSHSCRIPT_LOG": "debug"}
    )
    assert overridden.base_url == "http://127.0.0.1:1"
    assert overridden.log_level == "debug"


@pytest.mark.parametrize("timeout", [0, -1, True])
def test_timeout_must_be_positive(timeout: float) -> None:
    with pytest.raises(ConfigurationError, match="timeout"):
        resolve_config(TOKEN, timeout=timeout, env={})


@pytest.mark.parametrize("retries", [-1, True])
def test_max_retries_must_not_be_negative(retries: int) -> None:
    with pytest.raises(ConfigurationError, match="max_retries"):
        resolve_config(TOKEN, max_retries=retries, env={})


def test_unknown_log_level_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="log_level"):
        resolve_config(TOKEN, log_level="trace", env={})


def test_an_explicit_log_level_beats_the_environment() -> None:
    debug = {"HUSHSCRIPT_LOG": "debug"}
    assert resolve_config(TOKEN, log_level="off", env=debug).log_level == "off"
    assert resolve_config(TOKEN, env=debug).log_level == "debug"
    assert resolve_config(TOKEN, log_level="debug", env={}).log_level == "debug"
    assert resolve_config(TOKEN, env={"HUSHSCRIPT_LOG": ""}).log_level == "off"


def test_an_unknown_log_level_in_the_environment_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="log_level"):
        resolve_config(TOKEN, env={"HUSHSCRIPT_LOG": "trace"})


@pytest.mark.parametrize(
    "suffix", ["\x00", "\x1b[31m", "\x7f", "\u00e9", "\u00a0x", " x", "\tx", "a\nb", "\u200b"]
)
def test_a_token_with_control_or_non_printable_characters_is_refused(suffix: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        resolve_config(TOKEN + suffix, env={})
    surface = f"{raised.value} {raised.value!r} {raised.value.hint}"
    assert TOKEN[12:] not in surface
    assert suffix not in surface


def test_a_token_in_the_environment_is_checked_too() -> None:
    with pytest.raises(ConfigurationError, match="control or non-printable"):
        resolve_config(None, env={"HUSHSCRIPT_TOKEN": TOKEN[:20] + "\x07" + TOKEN[20:]})


def test_the_whitespace_around_a_token_is_still_stripped() -> None:
    assert resolve_config(f" \t{TOKEN}\r\n", env={}).credentials.token == TOKEN


def test_only_the_missing_token_carries_a_hint() -> None:
    assert "config_invalid" not in HINTS
    cases: list[dict[str, Any]] = [
        {"token": "nope"},
        {"token": TOKEN, "timeout": 0},
        {"token": TOKEN, "max_retries": -1},
        {"token": TOKEN, "base_url": "http://example.com"},
        {"token": TOKEN, "log_level": "loud"},
        {"token": "hsr1:eu:pat.\x01"},
    ]
    for kwargs in cases:
        with pytest.raises(ConfigurationError) as raised:
            resolve_config(env={}, **kwargs)
        assert raised.value.hint is None
    with pytest.raises(ConfigurationError) as missing:
        resolve_config(env={})
    assert missing.value.code == "config_invalid"
    assert missing.value.status is None
    assert missing.value.hint == (
        "Set HUSHSCRIPT_TOKEN or pass a token. Create one in the Hushscript app: "
        "Account → MCP (app.hushscript.com/account/mcp)."
    )


@pytest.mark.parametrize("client", [Hushscript, AsyncHushscript])
@pytest.mark.parametrize("token", ["", " \t\r\n", "hsr\x00bad", "hsr\x7fbad"])
def test_public_constructors_refuse_invalid_tokens_before_requests(
    client: type[Hushscript | AsyncHushscript],
    token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, {})])
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)
    with pytest.raises(ConfigurationError) as raised:
        client(token)
    assert (raised.value.code, raised.value.status) == ("config_invalid", None)
    assert script.requests == []


@pytest.mark.parametrize("client", [Hushscript, AsyncHushscript])
@pytest.mark.parametrize("environment", [False, True])
@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com",
        "https://api.example.com/path",
        "https://api.example.com?q=1",
        "https://api.example.com#fragment",
    ],
)
def test_public_constructors_validate_base_urls_from_either_source(
    client: type[Hushscript | AsyncHushscript],
    *,
    environment: bool,
    url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, {})])
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)
    if environment:
        monkeypatch.setenv("HUSHSCRIPT_BASE_URL", url)
    with pytest.raises(ConfigurationError) as raised:
        client(TOKEN, base_url=None if environment else url)
    assert (raised.value.code, raised.value.status) == ("config_invalid", None)
    assert script.requests == []


@pytest.mark.parametrize("client", [Hushscript, AsyncHushscript])
def test_an_explicit_base_url_beats_the_environment(
    client: type[Hushscript | AsyncHushscript],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://api.example.com")
    script = Script([reply(200)])
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)
    hs = client(TOKEN, base_url="https://api.explicit.example")
    assert hs._config.base_url == "https://api.explicit.example"  # pyright: ignore[reportPrivateUsage]
    if isinstance(hs, AsyncHushscript):
        asyncio.run(hs.aclose())
    else:
        hs.close()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["signup", "claim"])
@pytest.mark.parametrize("environment", [False, True])
@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com",
        "https://api.example.com/path",
        "https://api.example.com?q=1",
        "https://api.example.com#fragment",
    ],
)
def test_tokenless_entry_points_validate_base_urls_before_requests(
    *,
    asynchronous: bool,
    operation: str,
    environment: bool,
    url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, {})])
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)
    if environment:
        monkeypatch.setenv("HUSHSCRIPT_BASE_URL", url)
    base_url = None if environment else url

    def invoke() -> None:
        if asynchronous:
            if operation == "claim":
                asyncio.run(AsyncHushscript.agent_claim("signup", "secret", base_url=base_url))
            else:
                asyncio.run(
                    AsyncHushscript.agent_signup(
                        email="agent@example.com",
                        pack="45min",
                        accept_terms="version",
                        agent=AgentInfo(name="agent", platform="test"),
                        base_url=base_url,
                    )
                )
        elif operation == "claim":
            Hushscript.agent_claim("signup", "secret", base_url=base_url)
        else:
            Hushscript.agent_signup(
                email="agent@example.com",
                pack="45min",
                accept_terms="version",
                agent=AgentInfo(name="agent", platform="test"),
                base_url=base_url,
            )

    with pytest.raises(ConfigurationError) as raised:
        invoke()
    assert (raised.value.code, raised.value.status) == ("config_invalid", None)
    assert script.requests == []
