# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import httpx
import pytest

from conftest import TOKEN
from fakeapi import FakeApi, Job, error_reply
from hushscript import (
    AuthenticationError,
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
    assert transcript.raw["title"] == "Fake"
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
    with pytest.raises(UploadError):
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)


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
    assert api.count("POST", COMPLETE) == 0
    with pytest.raises(PreflightError):
        await hs.transcribe(media(), duration_seconds=100, concurrency=12)
    with pytest.raises(FileLimitError):
        await hs.transcribe(media(), duration_seconds=14.5)


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
    while not tokens or api.count("GET", r"/v1/jobs/[^/]+") < 3:  # noqa: ASYNC110
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = getattr(raised.value, "__notes__", [])
    assert any(tokens[0] in note for note in notes)


async def test_a_timeout_around_the_call_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(processing_polls=10**9)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
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
    while not api.jobs:  # noqa: ASYNC110
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = "\n".join(raised.value.__notes__)
    assert "k" * 24 in notes
    assert len(api.jobs) == 1


async def test_a_cancel_during_the_parts_names_the_key_and_the_resume_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_delay=30)
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
    while not api.r2_calls:  # noqa: ASYNC110
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    notes = "\n".join(raised.value.__notes__)
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
    with pytest.raises(UploadError):
        await hs.transcribe(
            media(), duration_seconds=100, concurrency=1, on_resume_token=tokens.append
        )
    broken["on"] = False

    class OneWay(io.BytesIO):
        def seekable(self) -> bool:
            return False

    with pytest.raises(UploadError) as raised:
        await hs.resume(tokens[0], OneWay(media(8999)))
    assert raised.value.code == "stream_size_mismatch"
    assert (await hs.resume(tokens[0], OneWay(media()))).id
    assert len(api.jobs) == 1
    await hs.aclose()
