from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import httpx
import pytest

from helpers import job_body, reply, transcript_body
from hushscript import ApiError, Job, NotFoundError, Page, PreflightError, Transcript
from hushscript._response import BadBodyError
from routes import async_hs_on, hs_on

if TYPE_CHECKING:
    from collections.abc import Mapping


def _utterance(speaker: str, text: str, start: int = 0, end: int = 1000) -> dict[str, object]:
    return {"speaker": speaker, "start_ms": start, "end_ms": end, "text": text}


def _body(
    utterances: list[dict[str, object]],
    names: dict[str, str] | None = None,
    translations: dict[str, object] | None = None,
) -> dict[str, object]:
    return transcript_body(
        speaker_names=names or {},
        body={
            "version": 1,
            "original": {"utterances": utterances},
            "translations": translations or {},
        },
    )


def test_a_transcript_carries_the_typed_fields_of_the_body() -> None:
    body = transcript_body(
        tags=["a", "b"], edited=True, auto_delete_at=1_700_086_400, language_detected=None
    )
    t = Transcript.from_api(body)
    assert (t.id, t.title, t.language, t.duration_seconds) == ("tr_1", "Weekly sync", None, 24)
    assert t.created_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert t.updated_at.tzinfo is UTC
    assert t.auto_delete_at == datetime(2023, 11, 15, 22, 13, 20, tzinfo=UTC)
    assert (t.tags, t.edited, t.languages, t.cleaned) == (["a", "b"], True, [], None)
    assert t.utterances[0].text == "Hi."
    assert isinstance(t.duration_seconds, int)


def test_the_speaker_name_is_the_saved_one_else_the_label_else_nothing() -> None:
    body = _body(
        [_utterance("A", "x"), _utterance("B", "y"), _utterance("", "z"), _utterance("C", "w")],
        names={"A": "  Dana  ", "B": " 　 "},
    )
    assert [u.speaker_name for u in Transcript.from_api(body).utterances] == [
        "Dana",
        "Speaker B",
        "",
        "Speaker C",
    ]


def test_translations_cleaned_and_the_language_fallback() -> None:
    body = _body(
        [_utterance("A", "hello")],
        translations={
            "es": {"utterances": [_utterance("A", "hola")]},
            "cleaned": {"utterances": [_utterance("A", "Hello.")]},
        },
    )
    t = Transcript.from_api(body)
    assert t.languages == ["es"]
    assert t.cleaned is not None
    assert t.cleaned[0].text == "Hello."
    assert t.utterances_for("es")[0].text == "hola"
    assert t.utterances_for("cleaned")[0].text == "Hello."
    assert t.utterances_for("fr") == t.utterances
    assert t.utterances_for() == t.utterances
    assert t.utterances_for("") == t.utterances
    assert t.utterances_for("original") == t.utterances
    assert "hola" in t.to_text("es")
    assert "hola" not in t.to_text("fr")


def test_text_is_to_text_and_the_raw_body_keeps_unknown_fields() -> None:
    body = transcript_body(x_unknown_field={"nested": True, "list": [1, 2, 3]})
    t = Transcript.from_api(body)
    assert t.text == t.to_text() == "Speaker A: Hi."
    raw: Mapping[str, object] = t.to_json()
    assert raw["x_unknown_field"] == {"nested": True, "list": [1, 2, 3]}
    assert raw["matter_code"] is None


def test_the_repr_does_not_show_the_transcript_text() -> None:
    t = Transcript.from_api(_body([_utterance("A", "a secret sentence")]))
    assert "secret" not in repr(t)
    assert "Weekly sync" not in repr(t)


def test_fractional_milliseconds_are_floored() -> None:
    t = Transcript.from_api(_body([{**_utterance("A", "x"), "start_ms": 1234.9, "end_ms": 2000.2}]))
    assert (t.utterances[0].start_ms, t.utterances[0].end_ms) == (1234, 2000)


def _without(body: dict[str, object], key: str) -> dict[str, object]:
    return {k: v for k, v in body.items() if k != key}


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ([], "expected an object"),
        (None, "expected an object"),
        (_without(transcript_body(), "created_at"), "created_at: expected a value"),
        (_without(transcript_body(), "id"), "id: expected a value"),
        (
            transcript_body(created_at="1700000000"),
            "created_at: expected a unix timestamp in seconds",
        ),
        (transcript_body(created_at=True), "created_at: expected a unix timestamp in seconds"),
        (transcript_body(created_at=-1), "created_at: expected a unix timestamp in seconds"),
        (transcript_body(created_at=10**30), "created_at: expected a unix timestamp in seconds"),
        (transcript_body(created_at=1.5), "created_at: expected a unix timestamp in seconds"),
        (
            transcript_body(duration_seconds=1.5),
            "duration_seconds: expected a whole number of 0 or more",
        ),
        (
            transcript_body(duration_seconds=-1),
            "duration_seconds: expected a whole number of 0 or more",
        ),
        (transcript_body(tags=[1]), "tags[0]: expected a string"),
        (transcript_body(speaker_names=[]), "speaker_names: expected an object"),
        (transcript_body(speaker_names={"A": 1}), "speaker_names.A: expected a string"),
        (transcript_body(edited="yes"), "edited: expected a boolean"),
        (
            transcript_body(body={"original": {"utterances": []}}),
            "body.translations: expected a value",
        ),
        (
            transcript_body(body={"original": {}, "translations": {}}),
            "body.original.utterances: expected a value",
        ),
        (
            _body([{"speaker": "A", "start_ms": float("nan"), "end_ms": 1, "text": "x"}]),
            "body.original.utterances[0].start_ms: expected a number",
        ),
        (
            _body([{"speaker": "A", "start_ms": 0, "end_ms": float("inf"), "text": "x"}]),
            "body.original.utterances[0].end_ms: expected a number",
        ),
        (
            _body([{"speaker": "A", "start_ms": True, "end_ms": 1, "text": "x"}]),
            "body.original.utterances[0].start_ms: expected a number",
        ),
        (
            _body([{"speaker": 1, "start_ms": 0, "end_ms": 1, "text": "x"}]),
            "body.original.utterances[0].speaker: expected a string",
        ),
        (
            _body([_utterance("A", "x")], translations={"es": {"utterances": "none"}}),
            "body.translations.es.utterances: expected an array",
        ),
    ],
)
def test_a_body_that_does_not_fit_is_refused(body: object, problem: str) -> None:
    with pytest.raises(BadBodyError) as raised:
        Transcript.from_api(body)
    assert str(raised.value) == f"transcript response ({problem})"


def test_a_transcript_without_created_at_is_a_bad_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _without(transcript_body(), "created_at")
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    with pytest.raises(ApiError) as raised:
        hs.transcripts.get("tr_1")
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        200,
        None,
    )
    assert "created_at" in str(raised.value)
    assert "Weekly sync" not in str(raised.value)


def test_get_reads_one_transcript_and_encodes_the_id(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, routes = hs_on(monkeypatch, lambda _request: reply(200, transcript_body("tr_x")))
    assert hs.transcripts.get("tr_x").id == "tr_x"
    hs.transcripts.get("a/b?c#d")
    assert routes.requests[0].url.path == "/v1/transcripts/tr_x"
    assert routes.requests[1].url.raw_path == b"/v1/transcripts/a%2Fb%3Fc%23d"


@pytest.mark.parametrize("bad_id", ["", None, 5])
def test_get_refuses_an_id_that_is_not_a_name(
    monkeypatch: pytest.MonkeyPatch, bad_id: object
) -> None:
    hs, routes = hs_on(monkeypatch, lambda _request: reply(200, transcript_body()))
    with pytest.raises(PreflightError, match="id is a non-empty string") as raised:
        hs.transcripts.get(bad_id)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


@pytest.mark.parametrize(
    "bad_id", ["", ".", "..", "\ud800", "ok\udfff", None, 42, 5, b"id", ["id"]]
)
def test_an_id_that_is_a_dot_segment_or_cannot_be_encoded_is_refused_everywhere(
    monkeypatch: pytest.MonkeyPatch, bad_id: object
) -> None:
    hs, routes = hs_on(monkeypatch, lambda _request: reply(200, transcript_body()))
    for call in (hs.transcripts.get, hs.jobs.get, hs.jobs.wait):
        with pytest.raises(PreflightError) as raised:
            call(bad_id)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


def test_an_id_that_only_contains_dots_is_an_ordinary_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, lambda _request: reply(200, transcript_body()))
    hs.transcripts.get("...")
    hs.transcripts.get("a.b")
    assert [r.url.raw_path for r in routes.requests] == [
        b"/v1/transcripts/...",
        b"/v1/transcripts/a.b",
    ]


def test_a_missing_transcript_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = httpx.Response(404, json={"error": "not_found", "code": 1000})
    hs, _ = hs_on(monkeypatch, lambda _request: missing)
    with pytest.raises(NotFoundError):
        hs.transcripts.get("tr_gone")


@pytest.mark.anyio
async def test_the_async_client_gets_a_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, transcript_body("tr_a")))
    transcript = await hs.transcripts.get("tr_a")
    assert transcript.id == "tr_a"
    assert "Hi." in transcript.to_srt()
    bad = _without(transcript_body(), "created_at")
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, bad))
    with pytest.raises(ApiError) as raised:
        await hs.transcripts.get("tr_a")
    assert raised.value.code == "bad_response"


def test_the_lists_and_the_raw_body_a_caller_gets_are_copies() -> None:
    t = Transcript.from_api(
        _body(
            [_utterance("A", "hello")],
            translations={"es": {"utterances": [_utterance("A", "hola")]}},
        )
    )
    t.utterances_for("es").clear()
    t.utterances_for().clear()
    t.utterances_for("").clear()
    t.utterances_for("zz").clear()
    assert [u.text for u in t.utterances_for("es")] == ["hola"]
    assert [u.text for u in t.utterances_for()] == ["hello"]
    assert t.utterances_for() is not t.utterances_for()
    raw = cast("dict[str, object]", t.to_json())
    raw["title"] = "changed"
    cast("dict[str, object]", cast("dict[str, object]", raw["body"])["original"]).clear()
    assert t.to_json()["title"] == "Weekly sync"
    assert t.to_srt() != ""
    assert t.to_json() is not t.to_json()


def test_every_value_that_holds_a_list_is_unhashable_by_design() -> None:
    t = Transcript.from_api(transcript_body())
    job = Job.from_body(job_body("job_1", "done"))
    values: tuple[object, ...] = (t, job, job.options, Page[object](items=[], next_cursor=None))
    for value in values:
        with pytest.raises(TypeError, match="unhashable"):
            hash(value)
        with pytest.raises(TypeError, match="unhashable"):
            set[object]().add(value)


def test_the_private_state_of_a_transcript_is_keyword_only() -> None:
    private = [f for f in fields(Transcript) if f.name in {"_raw", "_translations"}]
    assert len(private) == 2
    assert all(f.kw_only for f in private)
    assert not any(f.repr or f.compare for f in private)


def test_a_replaced_transcript_keeps_its_private_state() -> None:
    original = Transcript.from_api(
        _body(
            [_utterance("A", "hello")],
            translations={"es": {"utterances": [_utterance("A", "hola")]}},
        )
    )
    copy = replace(original, title="renamed")
    assert copy.title == "renamed"
    assert copy.to_json() == original.to_json()
    assert "hola" in copy.to_text("es")
    assert copy.to_srt("es") == original.to_srt("es")


@pytest.mark.parametrize("bad_id", ["", ".", "..", "\ud800", None, 42, 5])
@pytest.mark.anyio
async def test_async_resource_ids_are_rejected_before_any_request(
    monkeypatch: pytest.MonkeyPatch, bad_id: object
) -> None:
    hs, routes = async_hs_on(monkeypatch, lambda _r: reply(200, transcript_body()))
    for call in (hs.transcripts.get, hs.jobs.get, hs.jobs.wait):
        with pytest.raises(PreflightError) as raised:
            await call(bad_id)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


@pytest.mark.anyio
async def test_async_resource_ids_are_encoded_as_one_path_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v1/transcripts/"):
            return reply(200, transcript_body())
        return reply(200, job_body("a/b?c#d", "done"))

    hs, routes = async_hs_on(monkeypatch, handler)
    await hs.transcripts.get("a/b?c#d")
    await hs.jobs.get("a/b?c#d")
    await hs.jobs.wait("a/b?c#d")
    assert [request.url.raw_path for request in routes.requests] == [
        b"/v1/transcripts/a%2Fb%3Fc%23d",
        b"/v1/jobs/a%2Fb%3Fc%23d",
        b"/v1/jobs/a%2Fb%3Fc%23d",
    ]


def test_job_wait_propagates_the_callers_callback_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, lambda _r: reply(200, job_body("job_1", "queued")))
    failure = RuntimeError("caller failure")

    def on_progress(_progress: object) -> None:
        raise failure

    with pytest.raises(RuntimeError) as raised:
        hs.jobs.wait("job_1", on_progress=on_progress)
    assert raised.value is failure
    assert len(routes.requests) == 1


@pytest.mark.anyio
async def test_async_job_wait_propagates_the_callers_callback_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = async_hs_on(monkeypatch, lambda _r: reply(200, job_body("job_1", "queued")))
    failure = RuntimeError("caller failure")

    def on_progress(_progress: object) -> None:
        raise failure

    with pytest.raises(RuntimeError) as raised:
        await hs.jobs.wait("job_1", on_progress=on_progress)
    assert raised.value is failure
    assert len(routes.requests) == 1


NESTED_EXTRAS = [
    {},
    {"x_future": None},
    {"x_future": ""},
    {"x_future": " \t\u2003"},
    {"x_future": {"nested": [1, None, {"new": True}]}},
]


@pytest.mark.parametrize("extra", NESTED_EXTRAS)
def test_to_json_keeps_unknown_fields_of_every_nested_object(extra: dict[str, object]) -> None:
    utterance = {**_utterance("A", "Hi."), **extra}
    body = _body(
        [utterance],
        translations={
            "es": {"utterances": [utterance], **extra},
            "cleaned": {"utterances": [utterance]},
        },
    )
    body["body"] = {**cast("dict[str, object]", body["body"]), **extra}
    body.update(extra)
    transcript = Transcript.from_api(body)
    assert transcript.to_json() == body
    assert transcript.utterances_for("es")[0].text == "Hi."


def test_to_json_returns_a_deep_copy_of_the_nested_objects() -> None:
    utterance = {**_utterance("A", "Hi."), "x_future": {"nested": [1]}}
    body = _body([utterance])
    transcript = Transcript.from_api(body)
    raw = transcript.to_json()
    original = cast("dict[str, object]", cast("dict[str, object]", raw["body"])["original"])
    cast("list[dict[str, object]]", original["utterances"])[0]["text"] = "changed"
    assert transcript.to_json() == body
