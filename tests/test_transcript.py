from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest

from helpers import reply, transcript_body
from hushscript import ApiError, NotFoundError, PreflightError, Transcript
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
    assert t.utterances_for("fr") is t.utterances
    assert t.utterances_for() is t.utterances
    assert t.utterances_for("original") is t.utterances
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
    "body",
    [
        [],
        None,
        _without(transcript_body(), "created_at"),
        _without(transcript_body(), "id"),
        transcript_body(created_at="1700000000"),
        transcript_body(created_at=True),
        transcript_body(created_at=-1),
        transcript_body(created_at=10**30),
        transcript_body(created_at=1.5),
        transcript_body(duration_seconds=1.5),
        transcript_body(duration_seconds=-1),
        transcript_body(tags=[1]),
        transcript_body(speaker_names=[]),
        transcript_body(speaker_names={"A": 1}),
        transcript_body(edited="yes"),
        transcript_body(body={"original": {"utterances": []}}),
        transcript_body(body={"original": {}, "translations": {}}),
        _body([{"speaker": "A", "start_ms": float("nan"), "end_ms": 1, "text": "x"}]),
        _body([{"speaker": "A", "start_ms": 0, "end_ms": float("inf"), "text": "x"}]),
        _body([{"speaker": "A", "start_ms": True, "end_ms": 1, "text": "x"}]),
        _body([{"speaker": 1, "start_ms": 0, "end_ms": 1, "text": "x"}]),
        _body([_utterance("A", "x")], translations={"es": {"utterances": "none"}}),
    ],
)
def test_a_body_that_does_not_fit_is_refused(body: object) -> None:
    with pytest.raises(BadBodyError):
        Transcript.from_api(body)


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
        hs.transcripts.get(bad_id)  # pyright: ignore[reportArgumentType]
    assert raised.value.code == "invalid_option"
    assert routes.requests == []


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
