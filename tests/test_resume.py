from __future__ import annotations

import base64
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hushscript import ConfigurationError, ResumeMismatchError
from hushscript.transcribe.resume import (
    ResumeState,
    check_same_file,
    decode_token,
    encode_token,
    file_required,
)
from hushscript.transcribe.segment import usable_segment

STATE = ResumeState("job_1", "k" * 36, 1234, 21)


@given(
    st.text(min_size=1, max_size=40).filter(usable_segment),
    st.text(min_size=16, max_size=128),
    st.integers(min_value=1, max_value=5_000_000_000),
    st.integers(min_value=15, max_value=36000),
)
def test_a_token_round_trips(job: str, key: str, size: int, duration: int) -> None:
    state = ResumeState(job, key, size, duration)
    token = encode_token(state)
    assert decode_token(token) == state
    assert "=" not in token


def test_the_token_is_base64url_json_with_the_spec_keys() -> None:
    token = encode_token(STATE)
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    assert json.loads(raw) == {
        "v": 1,
        "jobId": "job_1",
        "idempotencyKey": "k" * 36,
        "size": 1234,
        "durationSeconds": 21,
    }


def _token(payload: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


@pytest.mark.parametrize(
    "token",
    [
        "",
        "%%%",
        "bm90IGpzb24",
        _token([1, 2]),
        _token({"v": 2, "jobId": "j", "idempotencyKey": "k", "size": 1, "durationSeconds": 1}),
        _token({"v": 1, "jobId": 5, "idempotencyKey": "k", "size": 1, "durationSeconds": 1}),
        _token({"v": 1, "jobId": "j", "idempotencyKey": "k", "size": True, "durationSeconds": 1}),
        _token({"v": 1, "jobId": "j", "idempotencyKey": "k", "size": 1}),
    ],
)
def test_a_token_that_is_not_ours_is_refused(token: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        decode_token(token)
    assert raised.value.code == "config_invalid"
    assert raised.value.status is None
    assert raised.value.hint is None


@pytest.mark.parametrize(
    ("token", "shown"),
    [
        ("%%%", " (JSONDecodeError: Expecting value: line 1 column 1 (char 0))"),
        ("eyJ2Ijo=", " (JSONDecodeError: Expecting value: line 1 column 6 (char 5))"),
        (_token([1, 2]), ""),
        (_token({"v": 2}), ""),
    ],
)
def test_a_token_that_does_not_decode_names_the_failure(token: str, shown: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        decode_token(token)
    assert raised.value.message == f"This is not a resume token from this SDK{shown}."


def test_a_file_of_another_size_is_refused() -> None:
    check_same_file(STATE, 1234)
    with pytest.raises(ResumeMismatchError) as raised:
        check_same_file(STATE, 1235)
    assert raised.value.code == "resume_file_mismatch"
    assert raised.value.status is None
    assert raised.value.hint is not None


def test_a_missing_file_is_its_own_code() -> None:
    error = file_required()
    assert error.code == "resume_file_required"
    assert error.hint is not None


@pytest.mark.parametrize("job_id", ["", ".", "..", "a/b", "a\\b", "../x"])
def test_a_token_naming_an_id_that_cannot_be_a_path_segment_is_refused(job_id: str) -> None:
    token = encode_token(ResumeState(job_id, "k" * 36, 1234, 21))
    with pytest.raises(ConfigurationError) as raised:
        decode_token(token)
    assert raised.value.code == "config_invalid"


def test_a_token_naming_an_id_with_awkward_characters_is_kept() -> None:
    state = ResumeState("j #?%é-1", "k" * 36, 1234, 21)
    assert decode_token(encode_token(state)) == state
