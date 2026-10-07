"""Mutated valid bodies through every 2xx mapper: the answer is a value or a HushscriptError.

A TypeError, KeyError, OverflowError or a stray ValueError out of a mapper would escape a public
method, so none may. The bodies go through JSON text, so `NaN`, `Infinity` and lone surrogates
arrive as they would from the API.
"""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any

import httpx
from hypothesis import given
from hypothesis import strategies as st

from conftest import TOKEN
from helpers import account_body, job_body, transcript_body
from hushscript import HushscriptError, Transcript
from hushscript._models import Job
from hushscript._redact import Credentials
from hushscript._response import parsed
from hushscript.resources.account import Account, Balance
from hushscript.resources.jobs import job_page
from hushscript.resources.transcripts import deleted_page, summary_page
from hushscript.transcribe.upload import parse_created

if TYPE_CHECKING:
    from collections.abc import Callable

Path = tuple[str | int, ...]

LISTED = {
    "id": "tr_1",
    "title": "T",
    "language_detected": None,
    "duration_seconds": 5,
    "created_at": 1_700_000_000,
    "auto_delete_at": 1_700_100_000,
    "tags": ["a"],
}
DELETED = {
    "id": "tr_1",
    "title": "T",
    "duration_seconds": 5,
    "created_at": 1_700_000_000,
    "deleted_at": 1_700_000_100,
    "cause": "manual",
    "receipt": {"k": "v"},
}
CREATED = {
    "job_id": "job_1",
    "state": "uploading",
    "upload": {
        "part_size_bytes": 100,
        "total_parts": 2,
        "part_urls": [{"n": 1, "url": "https://r2.test/1"}, {"n": 2, "url": "https://r2.test/2"}],
        "next_part_number": None,
    },
}
TRANSLATED = transcript_body(
    speaker_names={"A": "Dana"},
    tags=["x"],
    auto_delete_at=1_700_100_000,
    body={
        "version": 1,
        "original": {
            "utterances": [
                {"speaker": "A", "start_ms": 0, "end_ms": 4000, "text": "Hello there, world."},
                {"speaker": "B", "start_ms": 4000, "end_ms": 9000, "text": "Hi."},
            ]
        },
        "translations": {
            "es": {"utterances": [{"speaker": "A", "start_ms": 0, "end_ms": 4000, "text": "Hola"}]}
        },
    },
)

CASES: dict[str, tuple[Callable[[object], object], object]] = {
    "balance": (Balance.from_account, account_body(purchases_remaining_in_window=2)),
    "account": (Account.from_body, account_body(credits_expire_at=1_800_000_000)),
    "job": (Job.from_body, job_body("job_1", "done", transcript_id="tr_1")),
    "transcript": (Transcript.from_api, TRANSLATED),
    "transcripts": (summary_page, {"transcripts": [LISTED, LISTED], "next_cursor": "c"}),
    "deleted": (deleted_page, {"deleted": [DELETED], "next_cursor": None}),
    "jobs": (job_page, {"jobs": [job_body("job_1", "queued")], "next_cursor": "c"}),
    "created": (parse_created, CREATED),
}

SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**70), max_value=2**70),
    st.sampled_from([2**63, 2**63 - 1, -(2**63), 253_402_300_799, 253_402_300_800, 10**400]),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(alphabet=st.characters(exclude_categories=()), max_size=8),
)
VALUES = st.recursive(
    SCALARS,
    lambda children: st.one_of(
        st.lists(children, max_size=3), st.dictionaries(st.text(max_size=4), children, max_size=3)
    ),
    max_leaves=4,
)


def paths(value: object, prefix: Path = ()) -> list[Path]:
    found: list[Path] = [prefix]
    if isinstance(value, dict):
        for key, item in value.items():  # pyright: ignore[reportUnknownVariableType]
            found += paths(item, (*prefix, str(key)))  # pyright: ignore[reportUnknownArgumentType]
    elif isinstance(value, list):
        for index, item in enumerate(value):  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            found += paths(item, (*prefix, index))  # pyright: ignore[reportUnknownArgumentType]
    return found


def mutate(body: object, path: Path, replacement: object, *, delete: bool) -> object:
    if not path:
        return replacement
    root: Any = copy.deepcopy(body)
    parent: Any = root
    for step in path[:-1]:
        parent = parent[step]
    last = path[-1]
    if delete:
        del parent[last]
    else:
        parent[last] = replacement
    return root


@st.composite
def mutated(draw: st.DrawFn, base: object) -> object:
    path = draw(st.sampled_from(paths(base)))
    return mutate(base, path, draw(VALUES), delete=bool(path) and draw(st.booleans()))


def through_the_boundary(parse: Callable[[object], object], body: object) -> object:
    text = json.dumps(body, allow_nan=True)
    response = httpx.Response(
        200, content=text.encode(), headers={"content-type": "application/json"}
    )
    try:
        return parsed(response, Credentials(TOKEN), parse)
    except HushscriptError as error:
        failure = error
    assert (failure.code, failure.status, failure.numeric_code) == ("bad_response", 200, None)
    return None


def use(result: object) -> None:
    """What a caller does with a transcript: every formatter, in every option."""
    if not isinstance(result, Transcript):
        return
    for language in (None, "es", "cleaned", "zz"):
        for captions in (True, False):
            result.to_srt(language, captions=captions)
            result.to_vtt(language, captions=captions)
        for merge in (True, False):
            result.to_text(language, speakers=merge, timestamps=not merge, merge=merge)
    repr(result)


def run(name: str, body: object) -> None:
    parse, _ = CASES[name]
    use(through_the_boundary(parse, body))


@given(mutated(CASES["balance"][1]))
def test_balance_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("balance", body)


@given(mutated(CASES["account"][1]))
def test_account_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("account", body)


@given(mutated(CASES["job"][1]))
def test_job_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("job", body)


@given(mutated(CASES["transcript"][1]))
def test_transcript_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("transcript", body)


@given(mutated(CASES["transcripts"][1]))
def test_transcript_list_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("transcripts", body)


@given(mutated(CASES["deleted"][1]))
def test_deleted_list_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("deleted", body)


@given(mutated(CASES["jobs"][1]))
def test_job_list_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("jobs", body)


@given(mutated(CASES["created"][1]))
def test_upload_create_only_ever_answers_with_a_value_or_a_hushscript_error(body: object) -> None:
    run("created", body)


def test_every_unmutated_body_parses() -> None:
    for name, (parse, body) in CASES.items():
        assert through_the_boundary(parse, body) is not None, name
