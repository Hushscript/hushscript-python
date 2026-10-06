from __future__ import annotations

import pytest

from conftest import TOKEN
from hushscript import ConfigurationError, Hushscript
from hushscript._config import resolve_config


def test_refuses_construction_without_a_token_and_says_where_to_get_one() -> None:
    with pytest.raises(ConfigurationError, match="HUSHSCRIPT_TOKEN") as raised:
        Hushscript()
    assert raised.value.code == "config_invalid"
    assert raised.value.hint is not None
    assert raised.value.hint.startswith("Set HUSHSCRIPT_TOKEN or pass a token.")
    assert "app.hushscript.com/account/mcp" in raised.value.hint


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
