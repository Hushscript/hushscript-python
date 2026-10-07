from __future__ import annotations

import pickle
from urllib.parse import quote

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from conftest import TOKEN
from helpers import reply
from hushscript._errors import error_from_response
from hushscript._redact import REDACTED, TOKEN_PATTERN, Credentials, redact
from hushscript.resources.agent import read_answer


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


PUBLIC = "0123456789abcdef" * 2
SECRET = "fedcba9876543210" * 4


@pytest.mark.parametrize("piece", [SECRET, f"{PUBLIC}.{SECRET}", TOKEN])
def test_an_echoed_piece_of_the_token_is_scrubbed(piece: str) -> None:
    assert Credentials(TOKEN).scrub(f"echo {piece} end") == f"echo {REDACTED} end"
    assert Credentials(TOKEN).scrub(f"echo {piece.upper()} end") == f"echo {REDACTED} end"


def test_an_odd_token_loses_its_bare_secret_after_the_last_dot() -> None:
    odd = "hsr-odd.public." + "s3cretSEGMENTvalue99"
    assert Credentials(odd).scrub("x s3cretSEGMENTvalue99 x") == f"x {REDACTED} x"
    assert Credentials(odd).scrub("x " + odd.upper() + " x") == f"x {REDACTED} x"


def test_the_whole_token_is_scrubbed_in_its_percent_encoded_and_cased_forms() -> None:
    credentials = Credentials(TOKEN)
    encoded = quote(TOKEN, safe="")
    assert "%3A" in encoded
    for form in (encoded, encoded.lower(), TOKEN.upper(), TOKEN.replace(":", "%3a")):
        assert credentials.scrub(f"/v1/{form}/x") == f"/v1/{REDACTED}/x"


def test_a_short_segment_is_an_ordinary_substring() -> None:
    credentials = Credentials("hsr-odd.public.shortsecret")
    assert credentials.scrub("a shortsecret b") == "a shortsecret b"


def test_past_and_remembered_tokens_are_scrubbed_the_same_way() -> None:
    credentials = Credentials("hsr-old.id." + "o" * 20)
    credentials.replace("hsr-new.id." + "n" * 20)
    credentials.remember("hsr-seen.id." + "s" * 20)
    text = credentials.scrub(f"{'o' * 20} {'n' * 20} {'s' * 20}")
    assert text == f"{REDACTED} {REDACTED} {REDACTED}"


def test_a_remembered_token_is_taken_trimmed_from_an_answer() -> None:
    odd = "hsr1-odd-token-value-1234"
    credentials = Credentials()
    read_answer(reply(201, {"pat": f"  {odd}\n"}), credentials)
    assert credentials.scrub(f"echo {odd}") == f"echo {REDACTED}"


@pytest.mark.parametrize(
    "slug", [TOKEN, SECRET, f"{PUBLIC}.{SECRET}", TOKEN.upper(), quote(TOKEN, safe="")]
)
def test_a_server_slug_that_echoes_the_token_is_not_stored_in_the_code(slug: str) -> None:
    response = httpx.Response(418, json={"error": slug, "code": 1})
    error = error_from_response(response, credentials=Credentials(TOKEN))
    assert error.code == REDACTED
    assert SECRET not in repr(error) + str(error) + error.code
