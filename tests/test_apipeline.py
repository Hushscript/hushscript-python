# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import io
import json
import logging
from typing import TYPE_CHECKING

import async_timeout
import httpx
import pytest

from conftest import TOKEN
from fakeapi import FakeApi, Job, error_reply
from helpers import cancellation_notes
from hushscript import (
    AuthenticationError,
    ConfigurationError,
    FileLimitError,
    JobFailedError,
    PreflightError,
    ProcessingProgress,
    ResumeMismatchError,
    UploadError,
    UploadingProgress,
    WaitTimeoutError,
)
from hushscript.transcribe.resume import ResumeState, encode_token
from pipe import PipeClock, async_hs_for, media

if TYPE_CHECKING:
    from hushscript import Progress

R2 = r"/__r2/[^/]+/\d+"
PARTS = r"/v1/uploads/[^/]+/parts/\d+"
COMPLETE = r"/v1/uploads/[^/]+/complete"
PART_URLS = r"/v1/uploads/[^/]+/part-urls"
CREATE = "/v1/uploads"

pytestmark = pytest.mark.anyio


async def test_a_direct_upload_runs_on_tasks_and_sends_no_token_to_r2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=6)
    hs = async_hs_for(monkeypatch, api)
    seen: list[Progress] = []
    transcript = await hs.transcribe(media(), duration_seconds=100, on_progress=seen.append)
    assert transcript.to_json()["title"] == "Fake"
    assert api.count("PUT", R2) == 6
    assert all("authorization" not in r.headers for r in api.of("PUT", R2))
    assert [p.percent for p in seen if isinstance(p, UploadingProgress)][-1] == 100
    assert (
        any(isinstance(p, ProcessingProgress) for p in seen)
        or api.count("GET", r"/v1/jobs/[^/]+") >= 1
    )
    await hs.aclose()


async def test_a_proxied_upload_completes_without_a_body(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(proxied=True)
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100)
    assert (api.count("PUT", PARTS), api.count("PUT", R2)) == (1, 0)
    assert api.of("POST", COMPLETE)[0].content == b""


async def test_direct_failing_before_any_success_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda _n, _a: httpx.Response(500))
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100)
    assert api.count("PUT", PARTS) == 3


async def test_a_failing_part_after_a_success_stays_direct_and_exhausts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(503) if n == 2 else None)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "parts_exhausted"
    assert api.r2_calls[2] == 8
    assert api.count("POST", COMPLETE) == 0


async def test_network_failures_on_a_part_are_failed_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.ReadError("reset") if n == 3 else None)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "parts_exhausted"
    assert raised.value.status is None
    assert (
        raised.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"]
    )
    assert raised.value.resume_token == encode_token(
        ResumeState(
            "job_1", json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"], 9000, 100
        )
    )


async def test_expired_urls_and_paging(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(url_ttl_expired=True)
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100)
    assert api.count("GET", PART_URLS) >= 1
    assert api.count("PUT", PARTS) == 0
    api = FakeApi(parts=40)
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(4000), duration_seconds=100)
    assert [r.url.params["start"] for r in api.of("GET", PART_URLS)] == ["17", "33"]


async def test_a_forbidden_url_is_refreshed_once_then_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda _n, _a: httpx.Response(403))
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("PUT", PARTS) == 3
    assert api.r2_calls[1] == 2


async def test_a_part_finishing_direct_as_the_upload_switches_is_sent_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(500) if n == 1 else None)

    # Part 2 answers after part 1 has switched the upload: delay its direct PUT until a proxied
    # PUT has been seen.
    original = api.asynchronous()
    handler = original.handle_async_request

    async def delayed(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/__r2/job_1/2"):
            async with async_timeout.timeout(10):
                while not api.part_calls:  # noqa: ASYNC110
                    await asyncio.sleep(0.001)
        return await handler(request)

    monkeypatch.setattr(api, "asynchronous", lambda: httpx.MockTransport(delayed))
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100, concurrency=2)
    assert api.part_calls == {1: 1, 2: 1, 3: 1}
    assert api.of("POST", COMPLETE)[0].content == b""


async def test_upload_incomplete_done_failed_and_missing_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs = async_hs_for(monkeypatch, FakeApi(lose_parts=(2,)))
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100)
    assert raised.value.code == "upload_incomplete"
    api = FakeApi(complete_state="done")
    clock = PipeClock()
    hs = async_hs_for(monkeypatch, api, clock)
    await hs.transcribe(media(), duration_seconds=100)
    assert api.count("GET", r"/v1/jobs/[^/]+") == 1
    assert clock.sleeps == []
    api = FakeApi(failed={"error": "bad", "failure_kind": "media_unreadable"})
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(JobFailedError) as failed:
        await hs.transcribe(media(), duration_seconds=100, idempotency_key="z" * 20)
    assert failed.value.failure_kind == "media_unreadable"
    assert failed.value.idempotency_key == "z" * 20
    assert failed.value.resume_token
    hs = async_hs_for(monkeypatch, FakeApi(complete_state="done", drop_transcript_id=True))
    with pytest.raises(UploadError) as missing:
        await hs.transcribe(media(), duration_seconds=100)
    assert missing.value.code == "transcript_missing"


async def test_a_timed_out_wait_resumes_without_a_replay_and_jobs_wait_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(WaitTimeoutError) as raised:
        await hs.transcribe(
            media(), duration_seconds=100, wait_timeout=30, on_resume_token=tokens.append
        )
    assert tokens == [raised.value.resume_token]
    with pytest.raises(WaitTimeoutError):
        await hs.jobs.wait("job_1", wait_timeout=5)
    api.processing_polls = 0
    seen: list[Progress] = []
    assert (await hs.resume(tokens[0], media(), on_progress=seen.append)).id
    assert api.count("POST", CREATE) == 1
    assert (await hs.jobs.wait("job_1", on_progress=seen.append)).state == "done"


async def test_resume_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    token = encode_token(ResumeState("job_1", "k" * 36, 9000, 100))
    with pytest.raises(ResumeMismatchError) as gone:
        await hs.resume(token, media())
    assert gone.value.code == "resume_job_missing"
    with pytest.raises(ResumeMismatchError) as other:
        await hs.resume(token, media(9001))
    assert other.value.code == "resume_file_mismatch"
    api.jobs["job_1"] = Job("job_1", 9000, 3000, 3, "k" * 36)
    api.keys["k" * 36] = "job_1"
    with pytest.raises(ResumeMismatchError) as required:
        await hs.resume(token)
    assert required.value.code == "resume_file_required"
    before = api.count("POST", CREATE)
    assert before == 0
    wrong = httpx.Response(200, json={"job_id": "job_zzz", "state": "uploading", "upload": None})
    api.create_steps.append(wrong)
    with pytest.raises(ResumeMismatchError) as replaced:
        await hs.resume(token, media())
    assert replaced.value.code == "resume_job_missing"
    # Now let it finish: the replay returns the same job, which still has no parts.
    assert (await hs.resume(token, media())).id


async def test_stream_sizes_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(io.BytesIO(media()), size=8000, duration_seconds=100)
    assert raised.value.code == "stream_size_mismatch"
    assert raised.value.status is None
    assert (
        raised.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"]
    )
    assert raised.value.resume_token == encode_token(
        ResumeState(
            "job_1", json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"], 8000, 100
        )
    )
    assert api.count("POST", COMPLETE) == 0
    before = len(api.requests)
    with pytest.raises(PreflightError) as invalid:
        await hs.transcribe(media(), duration_seconds=100, concurrency=12)
    assert type(invalid.value) is PreflightError
    assert invalid.value.code == "invalid_option"
    assert invalid.value.status is None
    assert len(api.requests) == before
    with pytest.raises(FileLimitError) as short:
        await hs.transcribe(media(), duration_seconds=14.5)
    assert short.value.code == "duration_out_of_range"
    assert short.value.status is None
    assert len(api.requests) == before


async def test_an_unauthorized_heartbeat_aborts_the_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = PipeClock(beats=1)
    api = FakeApi(parts=6, heartbeat_steps=[error_reply(401, "unauthorized", 2000)], r2_delay=0.05)
    hs = async_hs_for(monkeypatch, api, clock)
    with pytest.raises(AuthenticationError):
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("POST", COMPLETE) == 0


async def test_a_heartbeat_is_sent_while_parts_are_slow(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = PipeClock(beats=1)
    api = FakeApi(parts=4, r2_delay=0.05)
    hs = async_hs_for(monkeypatch, api, clock)
    await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("POST", r"/v1/uploads/[^/]+/heartbeat") >= 1
    assert 120.0 in clock.sleeps


async def test_a_cancelled_call_stays_a_cancellation_and_names_the_way_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(processing_polls=10**9)
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    task = asyncio.ensure_future(
        hs.transcribe(
            media(), duration_seconds=100, wait_timeout=10**9, on_resume_token=tokens.append
        )
    )
    while not tokens or api.count("GET", r"/v1/jobs/[^/]+") < 3:
        assert not task.done(), "the call ended before it was polling"
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = cancellation_notes(raised.value)
    assert any(tokens[0] in note for note in notes)


async def test_a_timeout_around_the_call_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(processing_polls=10**9)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(asyncio.TimeoutError):
        async with async_timeout.timeout(0.05):
            await hs.transcribe(media(), duration_seconds=100, wait_timeout=10**9)


async def test_no_signed_url_or_token_reaches_any_logger(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    api = FakeApi(parts=3)
    hs = async_hs_for(monkeypatch, api, log_level="debug")
    with caplog.at_level(logging.DEBUG):
        await hs.transcribe(media(), duration_seconds=100)
    text = "\n".join(f"{r.name}: {r.getMessage()}" for r in caplog.records)
    assert api.count("PUT", R2) == 3
    assert "sig=" not in text
    assert "__r2" not in text
    assert TOKEN not in text
    assert "hushscript PUT r2:part/1 200" in text
    assert "httpx: HTTP Request: PUT r2:part/1" in text
    await hs.aclose()


async def test_a_cancel_while_the_create_response_is_held_names_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_delay=30)
    hs = async_hs_for(monkeypatch, api)
    task = asyncio.ensure_future(
        hs.transcribe(media(), duration_seconds=100, idempotency_key="k" * 24)
    )
    while not api.jobs:
        assert not task.done(), "the call ended before the create request was sent"
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = "\n".join(cancellation_notes(raised.value))
    assert "k" * 24 in notes
    assert len(api.jobs) == 1


async def test_a_cancel_during_the_parts_names_the_key_and_the_resume_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_delay=1)
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    task = asyncio.ensure_future(
        hs.transcribe(
            media(),
            duration_seconds=100,
            idempotency_key="k" * 24,
            on_resume_token=tokens.append,
        )
    )
    while not api.r2_calls:
        assert not task.done(), "the call ended before any part reached R2"
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = "\n".join(cancellation_notes(raised.value))
    assert "k" * 24 in notes
    assert tokens[0] in notes


async def test_resume_takes_a_stream_that_cannot_seek_with_the_size_from_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = {"on": True}

    def r2(n: int, _attempt: int) -> httpx.Response | None:
        return httpx.Response(503) if broken["on"] and n == 3 else None

    api = FakeApi(r2_hook=r2)
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(UploadError) as exhausted:
        await hs.transcribe(
            media(), duration_seconds=100, concurrency=1, on_resume_token=tokens.append
        )
    assert exhausted.value.code == "parts_exhausted"
    assert exhausted.value.status is None
    assert exhausted.value.resume_token == tokens[0]
    assert (
        exhausted.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"]
    )
    broken["on"] = False

    class OneWay(io.BytesIO):
        def seekable(self) -> bool:
            return False

    with pytest.raises(UploadError) as raised:
        await hs.resume(tokens[0], OneWay(media(8999)))
    assert raised.value.code == "stream_size_mismatch"
    assert raised.value.status is None
    assert raised.value.resume_token == tokens[0]
    assert (
        raised.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[-1].content)["idempotency_key"]
    )
    assert (await hs.resume(tokens[0], OneWay(media()))).id
    assert len(api.jobs) == 1
    await hs.aclose()


@pytest.mark.parametrize(
    "options",
    [
        {"idempotency_key": 123},
        {"idempotency_key": True},
        {"idempotency_key": []},
        {"idempotency_key": "x" * 15},
        {"idempotency_key": "x" * 129},
        {"idempotency_key": "x" * 15 + " "},
        {"idempotency_key": "x" * 15 + "é"},
        {"duration_seconds": True},
        {"duration_seconds": "20"},
        {"duration_seconds": float("nan")},
        {"duration_seconds": float("inf")},
        {"duration_seconds": 0},
        {"duration_seconds": -1},
        {"concurrency": True},
        {"concurrency": 0},
        {"concurrency": -1},
        {"concurrency": 1.5},
        {"concurrency": 9},
        {"wait_timeout": True},
        {"wait_timeout": 0},
        {"wait_timeout": float("nan")},
    ],
)
async def test_invalid_transcribe_options_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, object]
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    kwargs = {"duration_seconds": 100, **options}
    with pytest.raises(PreflightError) as raised:
        await hs.transcribe(media(), **kwargs)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert raised.value.idempotency_key is None
    assert raised.value.resume_token is None
    assert api.requests == []


@pytest.mark.parametrize("token", [None, 123, True, [], {}, b"abc", "", "nonsense"])
async def test_malformed_resume_tokens_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, token: object
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(ConfigurationError) as raised:
        await hs.resume(token)  # type: ignore[arg-type]
    assert raised.value.code == "config_invalid"
    assert raised.value.status is None
    assert raised.value.hint is None
    assert api.requests == []


@pytest.mark.parametrize(
    "options",
    [
        {"concurrency": 0},
        {"concurrency": -1},
        {"concurrency": 9},
        {"concurrency": 1.5},
        {"concurrency": True},
        {"wait_timeout": 0},
        {"wait_timeout": True},
    ],
)
async def test_invalid_resume_options_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, object]
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    token = encode_token(ResumeState("job_1", "k" * 36, 9000, 100))
    with pytest.raises(PreflightError) as raised:
        await hs.resume(token, **options)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert api.requests == []


@pytest.mark.parametrize("key", ["!" * 16, "~" * 128])
async def test_upload_key_boundaries_are_sent_unchanged(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    assert (
        await hs.transcribe(media(), duration_seconds=15, concurrency=8, idempotency_key=key)
    ).id
    assert json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"] == key


async def test_cancel_before_start_sends_no_request_and_has_no_recovery_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    task = asyncio.ensure_future(
        hs.transcribe(media(), duration_seconds=100, on_resume_token=tokens.append)
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    assert cancellation_notes(raised.value) == []
    assert api.requests == []
    assert tokens == []
    await hs.aclose()


@pytest.mark.parametrize(
    ("seconds", "accepted"), [(14.99, False), (15, True), (36000, True), (36000.01, False)]
)
async def test_duration_boundaries_place_no_hold_on_refusal(
    monkeypatch: pytest.MonkeyPatch, seconds: float, *, accepted: bool
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    if accepted:
        assert (await hs.transcribe(media(), duration_seconds=seconds)).id
        assert json.loads(api.of("POST", CREATE)[0].content)["duration_seconds"] == seconds
    else:
        with pytest.raises(FileLimitError) as raised:
            await hs.transcribe(media(), duration_seconds=seconds)
        assert raised.value.code == "duration_out_of_range"
        assert raised.value.status is None
        assert api.requests == []


@pytest.mark.parametrize(("age", "refreshes"), [(23 * 3600, 0), (23 * 3600 + 1, 1)])
async def test_part_urls_refresh_only_after_23_hours(
    monkeypatch: pytest.MonkeyPatch, age: int, refreshes: int
) -> None:
    clock = PipeClock()

    def advance(n: int, _attempt: int) -> None:
        if n == 1:
            clock.sleep(age)

    api = FakeApi(parts=2, r2_hook=advance)
    hs = async_hs_for(monkeypatch, api, clock)
    assert (await hs.transcribe(media(), duration_seconds=100, concurrency=1)).id
    assert api.count("GET", PART_URLS) == refreshes
    assert api.count("PUT", R2) == 2
    assert api.count("PUT", PARTS) == 0


@pytest.mark.parametrize("size", [True, False, 0, -1, 1.5, "9000", float("nan"), float("inf")])
async def test_invalid_stream_sizes_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, size: object
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        await hs.transcribe(io.BytesIO(media()), duration_seconds=100, size=size)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert api.requests == []


async def test_a_declared_stream_size_over_5_gb_sends_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(FileLimitError) as raised:
        await hs.transcribe(io.BytesIO(media()), size=5_000_000_001, duration_seconds=60)
    assert raised.value.code == "size_out_of_range"
    assert raised.value.status is None
    assert api.requests == []
