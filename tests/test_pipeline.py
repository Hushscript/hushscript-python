# pyright: reportPrivateUsage=false
from __future__ import annotations

import io
import json
import logging
import threading
import time
import tracemalloc
from typing import TYPE_CHECKING

import httpx
import pytest

from conftest import TOKEN
from fakeapi import FakeApi, Job, error_reply
from hushscript import (
    AuthenticationError,
    ConfigurationError,
    DailyLimitError,
    FileLimitError,
    InsufficientBalanceError,
    JobFailedError,
    PreflightError,
    ProcessingProgress,
    RateLimitError,
    ResumeMismatchError,
    UnsupportedMediaError,
    UploadError,
    UploadingProgress,
    WaitTimeoutError,
)
from hushscript.transcribe.resume import ResumeState, encode_token
from hushscript.transcribe.upload import MAX_PART_BYTES, proxied_plan
from pipe import PipeClock, hs_for, media

if TYPE_CHECKING:
    from pathlib import Path

    from hushscript import Progress

R2 = r"/__r2/[^/]+/\d+"
PARTS = r"/v1/uploads/[^/]+/parts/\d+"
COMPLETE = r"/v1/uploads/[^/]+/complete"
PART_URLS = r"/v1/uploads/[^/]+/part-urls"
CREATE = "/v1/uploads"


def _complete_body(api: FakeApi) -> bytes:
    return api.of("POST", COMPLETE)[0].content


def test_a_direct_upload_sends_the_parts_to_r2_without_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    transcript = hs.transcribe(media(), duration_seconds=100, title="My call")
    assert transcript.to_json()["title"] == "Fake"
    assert transcript.id.startswith("tr_job_1")
    assert api.count("POST", CREATE) == 1
    assert api.count("PUT", R2) == 3
    assert api.count("PUT", PARTS) == 0
    assert all("authorization" not in r.headers for r in api.of("PUT", R2))
    assert all("authorization" in r.headers for r in api.of("POST", CREATE))
    assert api.count("GET", "/v1/account") == 1
    assert b'"etag"' in _complete_body(api)
    assert b'"title":"My call"' in api.of("POST", CREATE)[0].content


def test_the_create_body_carries_the_options(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    hs.transcribe(
        media(),
        duration_seconds=100,
        language="en",
        speakers=False,
        keyterms=["acme"],
        matter_code="M-1",
        auto_insights=True,
        idempotency_key="k" * 24,
    )
    body = api.of("POST", CREATE)[0].content.decode()
    for part in ('"language_code":"en"', '"speaker_detection":false', '"acme"', '"M-1"'):
        assert part in body
    assert '"idempotency_key":"' + "k" * 24 in body


def test_a_proxied_upload_goes_through_the_api_and_completes_without_a_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(proxied=True)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100)
    assert (api.count("PUT", PARTS), api.count("PUT", R2)) == (1, 0)
    assert _complete_body(api) == b""
    put = api.of("PUT", PARTS)[0]
    assert put.headers["content-type"] == "application/octet-stream"
    assert "authorization" in put.headers


def test_a_pure_proxied_upload_is_cut_at_32_mib() -> None:
    plan = proxied_plan(MAX_PART_BYTES * 2 + 1)
    assert (plan.part_size, plan.total_parts) == (MAX_PART_BYTES, 3)
    assert proxied_plan(1).total_parts == 1


def test_every_direct_put_failing_before_any_success_falls_back_to_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda _n, _attempt: httpx.Response(500, text="boom"))
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("PUT", PARTS) == 3
    assert api.count("PUT", R2) == 4
    assert _complete_body(api) == b""
    assert sorted(put.url.path.rsplit("/", 1)[1] for put in api.of("PUT", PARTS)) == ["1", "2", "3"]


def test_a_part_that_keeps_failing_after_a_success_stays_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(
        parts=8,
        r2_hook=lambda n, attempt: httpx.Response(503) if n == 8 and attempt <= 5 else None,
    )
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(800), duration_seconds=100)
    assert api.count("PUT", R2) == 13
    assert api.count("PUT", PARTS) == 0
    assert api.count("GET", PART_URLS) == 1
    assert api.requests[0].url.path == "/v1/account"


def test_a_part_that_fails_all_its_rounds_raises_parts_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _attempt: httpx.Response(503) if n == 2 else None)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
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
    assert api.r2_calls[2] == 8
    assert api.count("GET", PART_URLS) == 1
    assert api.count("POST", COMPLETE) == 0


def test_a_failure_at_the_network_level_is_a_failed_round_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def hook(n: int, _attempt: int) -> httpx.Response | Exception | None:
        return httpx.ReadError("reset") if n == 3 else None

    api = FakeApi(r2_hook=hook)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
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
    assert api.r2_calls[3] == 8


def test_expired_urls_are_refetched_and_the_upload_stays_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(url_ttl_expired=True)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", PARTS) == 0
    assert api.direct_successes == 3


def test_a_url_that_stays_forbidden_is_refreshed_once_then_counts_as_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda _n, _attempt: httpx.Response(403, text="denied"))
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("PUT", PARTS) == 3
    assert api.r2_calls[1] == 2
    assert api.count("GET", PART_URLS) == 1


def test_part_url_pages_are_fetched_in_order_as_they_are_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=40)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(4000), duration_seconds=100)
    starts = [r.url.params["start"] for r in api.of("GET", PART_URLS)]
    assert starts == ["17", "33"]
    assert api.count("PUT", R2) == 40


def test_the_complete_body_lists_the_parts_in_order_with_unquoted_etags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=20)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(4000), duration_seconds=100)
    listed = httpx.Response(200, content=_complete_body(api)).json()["parts"]
    assert [part["n"] for part in listed] == list(range(1, 21))
    assert all('"' not in part["etag"] and len(part["etag"]) == 32 for part in listed)


def test_a_part_finishing_direct_as_the_upload_switches_is_sent_again_through_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxied_seen = threading.Event()

    def r2(n: int, _attempt: int) -> httpx.Response | None:
        if n == 1:
            return httpx.Response(500)
        if n == 2:
            proxied_seen.wait(10)
        return None

    def part(_n: int, _attempt: int) -> None:
        proxied_seen.set()

    api = FakeApi(r2_hook=r2, part_hook=part)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=2)
    assert api.part_calls == {1: 1, 2: 1, 3: 1}
    assert _complete_body(api) == b""


def test_complete_answering_upload_incomplete_is_an_upload_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(lose_parts=(2,))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "upload_incomplete",
        422,
        1041,
    )
    assert (
        raised.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"]
    )
    assert raised.value.resume_token == encode_token(
        ResumeState(
            "job_1", json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"], 9000, 100
        )
    )
    assert api.count("POST", COMPLETE) == 1


def test_a_complete_that_says_done_costs_one_job_read_and_no_poll_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(complete_state="done")
    clock = PipeClock()
    hs = hs_for(monkeypatch, api, clock)
    hs.transcribe(media(), duration_seconds=100)
    assert api.count("GET", r"/v1/jobs/[^/]+") == 1
    assert api.count("GET", r"/v1/transcripts/[^/]+") == 1
    assert clock.sleeps == []


def test_a_queued_job_is_polled_until_done(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(complete_state="queued", processing_polls=3)
    clock = PipeClock()
    seen: list[Progress] = []
    hs = hs_for(monkeypatch, api, clock)
    hs.transcribe(media(), duration_seconds=100, on_progress=seen.append)
    assert clock.sleeps == [5.0, 7.5, 11.25]
    states = [p.state for p in seen if isinstance(p, ProcessingProgress)]
    assert states == ["queued", "queued", "queued"]


def test_a_failed_job_raises_with_its_error_and_never_fetches_a_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(
        failed={"error": "Could not decode the audio", "failure_kind": "media_undecodable"}
    )
    hs = hs_for(monkeypatch, api)
    with pytest.raises(JobFailedError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert raised.value.failure_kind == "media_undecodable"
    assert raised.value.error == "Could not decode the audio"
    assert raised.value.job_id == "job_1"
    assert api.count("GET", r"/v1/transcripts/[^/]+") == 0


def test_a_done_job_without_a_transcript_id_raises_transcript_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(complete_state="done", drop_transcript_id=True)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert raised.value.code == "transcript_missing"


def test_the_resume_token_arrives_once_the_job_exists_and_resume_finishes_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(WaitTimeoutError) as raised:
        hs.transcribe(media(), duration_seconds=100, wait_timeout=60, on_resume_token=tokens.append)
    assert tokens == [raised.value.resume_token]
    assert raised.value.resume_token
    api.processing_polls = 0
    transcript = hs.resume(tokens[0], media())
    assert transcript.id
    # The job had left `uploading`, so there is nothing to replay: one job read, one create.
    assert api.count("POST", CREATE) == 1
    assert len(api.jobs) == 1
    assert api.count("PUT", R2) == 3
    assert api.requests[-3].url.path == "/v1/jobs/job_1"


def test_resume_refuses_a_file_of_another_size_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(WaitTimeoutError):
        hs.transcribe(media(), duration_seconds=100, wait_timeout=10, on_resume_token=tokens.append)
    before = len(api.requests)
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(tokens[0], media(9001))
    assert raised.value.code == "resume_file_mismatch"
    assert len(api.requests) == before


def test_resume_of_an_upload_that_never_finished_needs_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = {"on": True}

    def r2(n: int, _attempt: int) -> httpx.Response | None:
        return httpx.Response(503) if broken["on"] and n == 3 else None

    api = FakeApi(r2_hook=r2)
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(UploadError) as exhausted:
        hs.transcribe(media(), duration_seconds=100, concurrency=1, on_resume_token=tokens.append)
    assert exhausted.value.code == "parts_exhausted"
    assert exhausted.value.status is None
    assert exhausted.value.resume_token == tokens[0]
    assert (
        exhausted.value.idempotency_key
        == json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"]
    )
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(tokens[0])
    assert raised.value.code == "resume_file_required"
    assert raised.value.status is None
    broken["on"] = False
    assert hs.resume(tokens[0], media()).id
    assert len(api.jobs) == 1
    assert api.count("POST", CREATE) == 2
    keys = {
        httpx.Response(200, content=r.content).json()["idempotency_key"]
        for r in api.of("POST", CREATE)
    }
    assert len(keys) == 1


def test_a_resume_token_from_elsewhere_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ConfigurationError) as raised:
        hs.resume("nonsense")
    assert raised.value.code == "config_invalid"
    assert raised.value.status is None
    assert api.requests == []


def test_a_create_without_retry_after_waits_15_seconds_and_keeps_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_steps=[error_reply(429, "rate_limited", 5000)])
    clock = PipeClock()
    hs = hs_for(monkeypatch, api, clock)
    hs.transcribe(media(), duration_seconds=100)
    assert 15.0 in clock.sleeps
    assert api.count("POST", CREATE) == 2
    assert len(api.jobs) == 1


def test_a_create_whose_response_was_lost_is_replayed_with_the_same_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(drop_after_commit=1)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100)
    assert api.count("POST", CREATE) == 2
    assert len(api.jobs) == 1


def test_too_many_active_jobs_waits_30_seconds_between_tries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_steps=[error_reply(429, "too_many_active_jobs", 5001)])
    clock = PipeClock()
    hs = hs_for(monkeypatch, api, clock)
    hs.transcribe(media(), duration_seconds=100)
    assert 30.0 in clock.sleeps


def test_the_server_refusing_the_balance_surfaces_its_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = error_reply(
        402, "insufficient_balance", 3001, needed_seconds=21, balance_seconds=10, held_seconds=0
    )
    hs = hs_for(monkeypatch, FakeApi(create_steps=[step]))
    with pytest.raises(InsufficientBalanceError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert raised.value.status == 402
    assert raised.value.details["needed_seconds"] == 21


def test_six_files_in_a_loop_all_succeed_and_take_at_least_a_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(rate_limit_every=5)
    clock = PipeClock()
    hs = hs_for(monkeypatch, api, clock)
    for _ in range(6):
        assert hs.transcribe(media(), duration_seconds=100).id
    assert len(api.jobs) == 6
    assert clock.now() >= 60.0
    assert api.count("POST", CREATE) == 7


def test_upload_progress_counts_acknowledged_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(parts=4)
    seen: list[Progress] = []
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(4000), duration_seconds=100, concurrency=1, on_progress=seen.append)
    uploading = [p for p in seen if isinstance(p, UploadingProgress)]
    assert uploading[0] == UploadingProgress(0, 0, 4000)
    assert [p.bytes_sent for p in uploading] == [0, 1000, 2000, 3000, 4000]
    assert [p.percent for p in uploading] == [0, 25, 50, 75, 100]
    assert uploading[-1].stage == "uploading"


def test_the_wait_for_a_create_slot_reports_percent_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    for _ in range(5):
        hs.transcribe(media(), duration_seconds=100)
    seen: list[Progress] = []
    hs.transcribe(media(), duration_seconds=100, on_progress=seen.append)
    assert seen[0] == UploadingProgress(0, 0, 9000)
    assert hs._clock.now() >= 60.0


def test_a_path_a_stream_and_bytes_upload_the_same_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = media(5000)
    path = tmp_path / "talk.mp3"
    path.write_bytes(data)
    for given in (str(path), path, data, io.BytesIO(data)):
        api = FakeApi(parts=4)
        hs = hs_for(monkeypatch, api)
        hs.transcribe(given, duration_seconds=100)
        sent = b"".join(
            r.content
            for r in sorted(api.of("PUT", R2), key=lambda r: int(r.url.path.rsplit("/", 1)[1]))
        )
        assert sent == data


class OneWay(io.BytesIO):
    def seekable(self) -> bool:
        return False


def test_a_stream_that_cannot_seek_is_uploaded_in_order_one_part_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = media(5000)
    api = FakeApi(parts=4)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(OneWay(data), size=len(data), duration_seconds=100, concurrency=4)
    order = [int(r.url.path.rsplit("/", 1)[1]) for r in api.of("PUT", R2)]
    assert order == [1, 2, 3, 4]


def test_a_stream_that_cannot_seek_needs_size_and_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError):
        hs.transcribe(OneWay(media()), duration_seconds=100)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(OneWay(media()), size=9000)
    assert raised.value.code == "invalid_option"
    assert api.requests == []


def test_a_file_shorter_than_15_seconds_is_refused_with_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(FileLimitError) as raised:
        hs.transcribe(media(), duration_seconds=10)
    assert raised.value.code == "duration_out_of_range"
    assert api.requests == []


def test_a_file_that_is_not_media_is_refused_with_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UnsupportedMediaError) as raised:
        hs.transcribe(b"\x1a\x45\xdf\xa3" + bytes(100), duration_seconds=60)
    assert raised.value.code == "unsupported_media"
    assert raised.value.status is None
    assert raised.value.hint == (
        "Supported: MP3, M4A/MP4/MOV, WAV, FLAC, OGG/Opus. "
        "Convert it first, e.g. ffmpeg -i input -vn -c:a libopus output.opus"
    )
    assert api.requests == []


def test_a_bad_option_is_refused_with_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=99)
    assert raised.value.code == "invalid_option"
    with pytest.raises(PreflightError):
        hs.resume("x", wait_timeout=-1)
    assert api.requests == []


def test_a_balance_below_the_estimate_is_left_to_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = error_reply(
        402, "insufficient_balance", 3001, needed_seconds=21, balance_seconds=10, held_seconds=0
    )
    api = FakeApi(balance=10, create_steps=[step])
    hs = hs_for(monkeypatch, api)
    with pytest.raises(InsufficientBalanceError) as raised:
        hs.transcribe(media(), duration_seconds=21)
    assert raised.value.status == 402
    assert raised.value.details["balance_seconds"] == 10
    assert api.count("POST", CREATE) == 1
    assert api.count("GET", "/v1/account") == 1


def _wait_for_heartbeat(api: FakeApi) -> None:
    api.heartbeat_seen.wait(10)


def test_a_heartbeat_is_sent_while_the_upload_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = PipeClock(beats=1)
    api = FakeApi(r2_hook=lambda n, _attempt: _wait_for_heartbeat(api) if n == 2 else None)
    hs = hs_for(monkeypatch, api, clock)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("POST", r"/v1/uploads/[^/]+/heartbeat") == 1
    assert 120.0 in clock.sleeps


def test_an_unauthorized_heartbeat_aborts_the_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = PipeClock(beats=1)

    def r2(n: int, _attempt: int) -> None:
        if n >= 2:
            api.heartbeat_seen.wait(10)
        if n == 3:
            time.sleep(0.2)

    api = FakeApi(heartbeat_steps=[error_reply(401, "unauthorized", 2000)], r2_hook=r2)
    hs = hs_for(monkeypatch, api, clock)
    with pytest.raises(AuthenticationError):
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("POST", COMPLETE) == 0


def test_rate_limited_creates_that_never_clear_raise_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_steps=[error_reply(429, "rate_limited", 5000)] * 9)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(RateLimitError):
        hs.transcribe(media(), duration_seconds=100)
    assert api.count("POST", CREATE) == 4


def test_jobs_wait_polls_to_the_end(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(processing_polls=2)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100)
    job = hs.jobs.wait("job_1")
    assert job.state == "done"
    seen: list[Progress] = []
    api.jobs["job_1"].state = "processing"
    api.jobs["job_1"].polls = 0
    assert hs.jobs.wait("job_1", on_progress=seen.append).state == "done"
    assert seen


def test_jobs_wait_times_out_without_a_resume_token(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(WaitTimeoutError):
        hs.transcribe(media(), duration_seconds=100, wait_timeout=1)
    with pytest.raises(WaitTimeoutError) as raised:
        hs.jobs.wait("job_1", wait_timeout=10)
    assert raised.value.resume_token is None


def _token(job_id: str = "job_1", key: str = "k" * 36, size: int = 9000) -> str:
    return encode_token(ResumeState(job_id, key, size, 100))


def test_a_job_that_no_longer_exists_is_not_replayed(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(_token("job_gone"), media())
    assert raised.value.code == "resume_job_missing"
    assert raised.value.hint is not None
    assert [r.url.path for r in api.requests] == ["/v1/jobs/job_gone"]


def test_a_replay_that_names_another_job_stops_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    other = httpx.Response(200, json={"job_id": "job_other", "state": "uploading", "upload": None})
    api = FakeApi(create_steps=[other])
    hs = hs_for(monkeypatch, api)
    api.jobs["job_1"] = Job("job_1", 9000, None, None, "k" * 36)
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(_token(), media())
    assert raised.value.code == "resume_job_missing"
    assert [r.url.path for r in api.requests] == ["/v1/jobs/job_1", CREATE]


def test_resume_of_an_uploading_job_without_a_file_does_not_replay_the_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    api.jobs["job_1"] = Job("job_1", 9000, None, None, "k" * 36)
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(_token())
    assert raised.value.code == "resume_file_required"
    assert api.count("POST", CREATE) == 0


@pytest.mark.parametrize("declared", [8999, 9001])
def test_a_stream_of_another_size_than_declared_never_completes(
    monkeypatch: pytest.MonkeyPatch, declared: int
) -> None:
    api = FakeApi(parts=3)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(OneWay(media()), size=declared, duration_seconds=100)
    assert raised.value.code == "stream_size_mismatch"
    assert raised.value.hint is not None
    assert api.count("POST", COMPLETE) == 0


@pytest.mark.parametrize("declared", [8000, 9500])
def test_a_seekable_stream_of_another_size_than_declared_never_completes(
    monkeypatch: pytest.MonkeyPatch, declared: int
) -> None:
    api = FakeApi(parts=3)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(io.BytesIO(media()), size=declared, duration_seconds=100)
    assert raised.value.code == "stream_size_mismatch"
    assert api.count("POST", COMPLETE) == 0


def test_a_file_that_shrinks_during_the_upload_is_an_upload_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "a.mp3"
    path.write_bytes(media())
    api = FakeApi(parts=3)

    def shrink(n: int, _attempt: int) -> None:
        if n == 1:
            path.write_bytes(media(100))

    api.r2_hook = shrink
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(path, duration_seconds=100, concurrency=1)
    assert raised.value.code == "upload_incomplete"


@pytest.mark.parametrize("size", [0, -5, 2.5, True, "9000"])
def test_a_stream_size_that_is_not_a_positive_whole_number_is_refused(
    monkeypatch: pytest.MonkeyPatch, size: object
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(OneWay(media()), size=size, duration_seconds=100)  # type: ignore[arg-type]
    assert raised.value.code == "invalid_option"
    assert api.requests == []


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), -1, 0, "20"])
def test_a_duration_that_is_not_a_finite_positive_number_is_invalid(
    monkeypatch: pytest.MonkeyPatch, seconds: object
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(media(), duration_seconds=seconds)  # type: ignore[arg-type]
    assert raised.value.code == "invalid_option"
    assert api.requests == []


@pytest.mark.parametrize("seconds", [14.5, 14.999, 36000.5])
def test_a_finite_duration_outside_the_range_is_a_file_limit(
    monkeypatch: pytest.MonkeyPatch, seconds: float
) -> None:
    hs = hs_for(monkeypatch, FakeApi())
    with pytest.raises(FileLimitError) as raised:
        hs.transcribe(media(), duration_seconds=seconds)
    assert raised.value.code == "duration_out_of_range"


@pytest.mark.parametrize("concurrency", [0, 9, 100, -1])
def test_concurrency_outside_1_to_8_is_refused_never_clamped(
    monkeypatch: pytest.MonkeyPatch, concurrency: int
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=concurrency)
    assert raised.value.code == "invalid_option"
    assert api.requests == []


def test_an_error_after_the_create_carries_the_key_and_the_resume_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(failed={"error": "no", "failure_kind": "media_undecodable"})
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(JobFailedError) as raised:
        hs.transcribe(
            media(),
            duration_seconds=100,
            idempotency_key="my-own-key-0123456789",
            on_resume_token=tokens.append,
        )
    assert raised.value.idempotency_key == "my-own-key-0123456789"
    assert raised.value.resume_token == tokens[0]


def test_an_error_from_the_create_itself_carries_the_key_but_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_steps=[error_reply(402, "insufficient_balance", 3001)])
    hs = hs_for(monkeypatch, api)
    with pytest.raises(InsufficientBalanceError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert (
        raised.value.idempotency_key
        == api.of("POST", CREATE)[0].content.decode().split('"idempotency_key":"')[1][:36]
    )
    assert raised.value.resume_token is None


def test_a_preflight_error_has_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    hs = hs_for(monkeypatch, FakeApi(used_today=36000))
    with pytest.raises(DailyLimitError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert raised.value.idempotency_key is None


def test_passing_the_key_back_replays_the_same_job(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(WaitTimeoutError) as raised:
        hs.transcribe(media(), duration_seconds=100, wait_timeout=10)
    api.processing_polls = 0
    key = raised.value.idempotency_key
    assert key is not None
    assert hs.transcribe(media(), duration_seconds=100, idempotency_key=key).id
    assert len(api.jobs) == 1


@pytest.mark.parametrize("source_kind", ["path", "stream", "bytes"])
def test_memory_stays_at_concurrency_times_part_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source_kind: str
) -> None:
    parts, part_size, width = 16, 1 << 20, 2
    data = media(parts * part_size)
    path = tmp_path / "big.mp3"
    path.write_bytes(data)
    stream = path.open("rb")
    given: object = {"path": path, "stream": stream, "bytes": data}[source_kind]
    api = FakeApi(parts=parts, retain_bodies=False)
    hs = hs_for(monkeypatch, api)
    tracemalloc.start()
    try:
        hs.transcribe(given, duration_seconds=100, concurrency=width)  # type: ignore[arg-type]
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        stream.close()
    held = len(data) if source_kind == "bytes" else 0
    # Two parts in flight, one copy each, and the harness's own transient copy of the part it is
    # answering; far below the 16 MiB of the file.
    assert peak - held < (width + 1) * part_size + (1 << 20)


# --- fix round: log redaction, interrupt notes, resume of a stream ---


def test_no_signed_url_or_token_reaches_any_logger(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    api = FakeApi(parts=3)
    hs = hs_for(monkeypatch, api, log_level="debug")
    with caplog.at_level(logging.DEBUG):
        hs.transcribe(media(), duration_seconds=100)
    text = "\n".join(f"{r.name}: {r.getMessage()}" for r in caplog.records)
    assert api.count("PUT", R2) == 3
    assert "sig=" not in text
    assert "__r2" not in text
    assert TOKEN not in text
    assert "hushscript PUT r2:part/1 200" in text
    assert "httpx: HTTP Request: PUT r2:part/1" in text  # httpx's own line, URL swapped out


def test_another_httpx_users_urls_are_left_alone(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    api = FakeApi()
    hs_for(monkeypatch, api, log_level="debug")
    with (
        caplog.at_level(logging.INFO, logger="httpx"),
        httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200))) as other,
    ):
        other.get("https://example.test/a?b=1")
    assert any("https://example.test/a?b=1" in r.getMessage() for r in caplog.records)


def test_an_interrupt_during_the_create_names_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    api = FakeApi(after_create=interrupt)  # the job is committed, the response never arrives
    hs = hs_for(monkeypatch, api)
    with pytest.raises(KeyboardInterrupt) as raised:
        hs.transcribe(media(), duration_seconds=100, idempotency_key="k" * 24)
    notes = "\n".join(raised.value.__notes__)
    assert "k" * 24 in notes
    assert len(api.jobs) == 1


def test_an_interrupt_during_the_parts_names_the_key_and_the_resume_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt(_n: int, _attempt: int) -> httpx.Response | None:
        raise KeyboardInterrupt

    api = FakeApi(r2_hook=interrupt)
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(KeyboardInterrupt) as raised:
        hs.transcribe(
            media(),
            duration_seconds=100,
            concurrency=1,
            idempotency_key="k" * 24,
            on_resume_token=tokens.append,
        )
    notes = "\n".join(raised.value.__notes__)
    assert "k" * 24 in notes
    assert tokens[0] in notes


def test_an_interrupt_before_the_create_is_sent_carries_no_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt(_event: Progress) -> None:
        raise KeyboardInterrupt

    hs = hs_for(monkeypatch, FakeApi())
    with pytest.raises(KeyboardInterrupt) as raised:
        hs.transcribe(media(), duration_seconds=100, on_progress=interrupt)
    assert not getattr(raised.value, "__notes__", [])


def _broken_upload(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeApi, str, dict[str, bool]]:
    broken = {"on": True}

    def r2(n: int, _attempt: int) -> httpx.Response | None:
        return httpx.Response(503) if broken["on"] and n == 3 else None

    api = FakeApi(r2_hook=r2)
    tokens: list[str] = []
    with pytest.raises(UploadError):
        hs_for(monkeypatch, api).transcribe(
            media(), duration_seconds=100, concurrency=1, on_resume_token=tokens.append
        )
    return api, tokens[0], broken


def test_resume_takes_a_stream_that_cannot_seek_with_the_size_from_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, token, broken = _broken_upload(monkeypatch)
    broken["on"] = False
    transcript = hs_for(monkeypatch, api).resume(token, OneWay(media()))
    assert transcript.id
    assert len(api.jobs) == 1
    assert api.count("POST", COMPLETE) == 1


@pytest.mark.parametrize("size", [8999, 9001])
def test_resume_still_refuses_a_stream_of_another_size(
    monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    api, token, broken = _broken_upload(monkeypatch)
    broken["on"] = False
    with pytest.raises(UploadError) as raised:
        hs_for(monkeypatch, api).resume(token, OneWay(media(size)))
    assert raised.value.code == "stream_size_mismatch"
    assert api.count("POST", COMPLETE) == 0


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
def test_invalid_transcribe_options_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, object]
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    kwargs = {"duration_seconds": 100, **options}
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(media(), **kwargs)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert raised.value.idempotency_key is None
    assert raised.value.resume_token is None
    assert api.requests == []


@pytest.mark.parametrize("token", [None, 123, True, [], {}, b"abc", "", "nonsense"])
def test_malformed_resume_tokens_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, token: object
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ConfigurationError) as raised:
        hs.resume(token)  # type: ignore[arg-type]
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
def test_invalid_resume_options_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, object]
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    token = encode_token(ResumeState("job_1", "k" * 36, 9000, 100))
    with pytest.raises(PreflightError) as raised:
        hs.resume(token, **options)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert api.requests == []


@pytest.mark.parametrize("key", ["!" * 16, "~" * 128])
def test_upload_key_boundaries_are_sent_unchanged(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    assert (hs.transcribe(media(), duration_seconds=15, concurrency=8, idempotency_key=key)).id
    assert json.loads(api.of("POST", CREATE)[0].content)["idempotency_key"] == key


@pytest.mark.parametrize(("age", "refreshes"), [(23 * 3600, 0), (23 * 3600 + 1, 1)])
def test_part_urls_refresh_only_after_23_hours(
    monkeypatch: pytest.MonkeyPatch, age: int, refreshes: int
) -> None:
    clock = PipeClock()

    def advance(n: int, _attempt: int) -> None:
        if n == 1:
            clock.sleep(age)

    api = FakeApi(parts=2, r2_hook=advance)
    hs = hs_for(monkeypatch, api, clock)
    assert hs.transcribe(media(), duration_seconds=100, concurrency=1).id
    assert api.count("GET", PART_URLS) == refreshes
    assert api.count("PUT", R2) == 2
    assert api.count("PUT", PARTS) == 0


@pytest.mark.parametrize(
    ("seconds", "accepted"), [(14.99, False), (15, True), (36000, True), (36000.01, False)]
)
def test_duration_boundaries_place_no_hold_on_refusal(
    monkeypatch: pytest.MonkeyPatch, seconds: float, *, accepted: bool
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    if accepted:
        assert (hs.transcribe(media(), duration_seconds=seconds)).id
        assert json.loads(api.of("POST", CREATE)[0].content)["duration_seconds"] == seconds
    else:
        with pytest.raises(FileLimitError) as raised:
            hs.transcribe(media(), duration_seconds=seconds)
        assert raised.value.code == "duration_out_of_range"
        assert raised.value.status is None
        assert api.requests == []


@pytest.mark.parametrize("size", [True, False, 0, -1, 1.5, "9000", float("nan"), float("inf")])
def test_invalid_stream_sizes_never_send_a_request(
    monkeypatch: pytest.MonkeyPatch, size: object
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(io.BytesIO(media()), duration_seconds=100, size=size)  # type: ignore[arg-type]
    assert type(raised.value) is PreflightError
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None
    assert api.requests == []


def test_a_declared_stream_size_over_5_gb_sends_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(FileLimitError) as raised:
        hs.transcribe(io.BytesIO(media()), size=5_000_000_001, duration_seconds=60)
    assert raised.value.code == "size_out_of_range"
    assert raised.value.status is None
    assert api.requests == []
