from __future__ import annotations

import pickle

import pytest
from hypothesis import given
from hypothesis import strategies as st

from conftest import TOKEN
from hushscript._redact import REDACTED, TOKEN_PATTERN, Credentials, redact


def _token(version: int, region: str, public: str, secret: str) -> str:
    return f"hsr{version}:{region}:pat.{public}.{secret}"


TOKENS = st.builds(
    _token,
    st.integers(min_value=0, max_value=99),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6),
    st.text(alphabet="0123456789abcdef", min_size=1, max_size=40),
    st.text(alphabet="0123456789abcdef", min_size=1, max_size=70),
)


def test_redact_replaces_a_token_shaped_substring() -> None:
    assert redact(f"bad token {TOKEN}!") == f"bad token {REDACTED}!"
    assert REDACTED == "hsr…[redacted]"


@given(TOKENS, st.text(max_size=30), st.text(max_size=30))
def test_a_token_shape_never_survives_redaction(token: str, before: str, after: str) -> None:
    assert TOKEN_PATTERN.search(redact(f"{before} {token} {after}")) is None


def test_credentials_scrub_the_exact_token_even_when_the_format_is_unusual() -> None:
    credentials = Credentials("hsr-odd-token-value")
    assert credentials.scrub("echo hsr-odd-token-value") == f"echo {REDACTED}"


def test_credentials_remember_rotated_tokens() -> None:
    credentials = Credentials("hsr-old")
    credentials.replace("hsr-new")
    assert credentials.token == "hsr-new"
    assert credentials.scrub("hsr-old hsr-new") == f"{REDACTED} {REDACTED}"


def test_credentials_without_a_token() -> None:
    credentials = Credentials()
    assert credentials.token is None
    assert credentials.scrub("plain") == "plain"


def test_scrub_value_walks_containers() -> None:
    credentials = Credentials(TOKEN)
    scrubbed = credentials.scrub_value({"a": [TOKEN, ("x", TOKEN)], TOKEN: {"b": 1}, "n": None})
    assert scrubbed == {"a": [REDACTED, ["x", REDACTED]], REDACTED: {"b": 1}, "n": None}


def test_credentials_never_show_the_token() -> None:
    credentials = Credentials(TOKEN)
    assert TOKEN[12:] not in repr(credentials) + str(credentials) + str(
        vars(credentials) if hasattr(credentials, "__dict__") else ""
    )
    with pytest.raises(TypeError, match="pickled"):
        pickle.dumps(credentials)
