# pyright: reportPrivateUsage=false
from __future__ import annotations

import io
import json
import os
import threading
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
import pytest

from fakeapi import FakeApi, error_reply
from hushscript import (
    ApiError,
    NotFoundError,
    PreflightError,
    ResumeMismatchError,
    UploadError,
    UploadingProgress,
    WaitTimeoutError,
)
from hushscript._response import BadBodyError
from hushscript.transcribe.source import PathSource
from hushscript.transcribe.upload import (
    MAX_PART_BYTES,
    Action,
    Mode,
    PartAttempts,
    UploadState,
    parse_plan,
)
from pipe import PipeClock, async_hs_for, hs_for, media

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from hushscript import Hushscript, Progress

CREATE = "/v1/uploads"
COMPLETE = r"/v1/uploads/[^/]+/complete"
JSON = {"content-type": "application/json"}

pytestmark = pytest.mark.anyio


# --- an input that cannot be read (spec 9.2: file_unreadable, source_read_failed) ---


def test_a_missing_path_is_file_unreadable_with_the_os_error_and_no_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(tmp_path / "missing.mp3", duration_seconds=100)
    missing = tmp_path / "missing.mp3"
    assert raised.value.code == "file_unreadable"
    assert raised.value.message == (
        f"The file {missing} cannot be read "
        f"(FileNotFoundError: [Errno 2] No such file or directory: '{missing}')."
    )
    assert isinstance(raised.value.__cause__, FileNotFoundError)
    assert api.requests == []


def test_a_directory_is_file_unreadable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(tmp_path, duration_seconds=100)
    assert raised.value.code == "file_unreadable"
    assert api.requests == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root opens any file")
def test_a_file_that_cannot_be_opened_is_file_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "locked.mp3"
    path.write_bytes(media())
    path.chmod(0)
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(path, duration_seconds=100)
    assert raised.value.code == "file_unreadable"
    assert isinstance(raised.value.__cause__, PermissionError)
    assert api.requests == []


async def test_async_a_missing_path_is_file_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi()
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        await hs.transcribe(tmp_path / "missing.mp3", duration_seconds=100)
    assert raised.value.code == "file_unreadable"
    assert api.requests == []


class Flaky(io.BytesIO):
    failing = False

    def read(self, size: int | None = -1, /) -> bytes:
        if self.failing:
            raise OSError("disk went away")
        return super().read(size)


def test_a_read_failure_in_the_middle_of_the_upload_is_source_read_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = Flaky(media())

    def cut(n: int, _attempt: int) -> None:
        if n == 1:
            stream.failing = True

    api = FakeApi(r2_hook=cut)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(stream, duration_seconds=100, concurrency=1)
    assert raised.value.code == "source_read_failed"
    assert (
        raised.value.message == "Part 2 could not be read from the file (OSError: disk went away)."
    )
    assert isinstance(raised.value.__cause__, OSError)
    assert api.count("POST", COMPLETE) == 0
    assert raised.value.resume_token


async def test_async_a_read_failure_is_source_read_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "a.mp3"
    path.write_bytes(media())
    original = PathSource.read_range

    def failing(self: PathSource, offset: int, length: int) -> bytes:
        if offset > 0:
            raise OSError("disk went away")
        return original(self, offset, length)

    monkeypatch.setattr(PathSource, "read_range", failing)
    hs = async_hs_for(monkeypatch, FakeApi())
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(path, duration_seconds=100, concurrency=1)
    assert raised.value.code == "source_read_failed"


# --- a 2xx body the SDK cannot use is bad_response ---

UNUSABLE = [
    pytest.param(lambda: httpx.Response(200, json={}), 200, id="empty-object"),
    pytest.param(lambda: httpx.Response(200, content=b"null", headers=JSON), 200, id="null"),
    pytest.param(lambda: httpx.Response(201, text="<html>nope</html>"), 201, id="not-json"),
    pytest.param(lambda: httpx.Response(200, json={"job_id": 7}), 200, id="wrong-type"),
]


@pytest.mark.parametrize(("build", "status"), UNUSABLE)
def test_an_unusable_create_response_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, build: Callable[[], httpx.Response], status: int
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, build))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert type(raised.value) is ApiError
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        status,
        None,
    )
    assert raised.value.idempotency_key


@pytest.mark.parametrize(("build", "status"), UNUSABLE[:3])
async def test_async_an_unusable_create_response_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, build: Callable[[], httpx.Response], status: int
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, build))
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        await hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status) == ("bad_response", status)


def test_an_unusable_job_transcript_and_balance_are_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    api.overrides.append(("GET", "/v1/jobs/.+", lambda: httpx.Response(200, json={})))
    with pytest.raises(ApiError) as job:
        hs.jobs.wait("job_9")
    assert job.value.code == "bad_response"
    api.overrides.clear()
    api.overrides.append(
        ("GET", "/v1/transcripts/.+", lambda: httpx.Response(200, content=b"null", headers=JSON))
    )
    with pytest.raises(ApiError) as transcript:
        hs.transcribe(media(), duration_seconds=100)
    assert (transcript.value.code, transcript.value.status) == ("bad_response", 200)
    api.overrides.clear()
    api.overrides.append(("GET", "/v1/account", lambda: httpx.Response(200, json={})))
    with pytest.raises(ApiError) as balance:
        hs.balance()
    assert (balance.value.code, balance.value.numeric_code) == ("bad_response", None)


def test_an_error_status_is_still_its_own_error_not_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    api.overrides.append(("GET", "/v1/account", lambda: error_reply(500, "internal", 9000)))
    hs = hs_for(monkeypatch, api, max_retries=0)
    with pytest.raises(ApiError) as raised:
        hs.balance()
    assert raised.value.code != "bad_response"


# --- the upload plan and the part URLs ---


def _plan(part: object, total: object) -> httpx.Response:
    upload: dict[str, object] = {
        "part_size_bytes": part,
        "total_parts": total,
        "part_urls": [],
        "next_part_number": None,
    }
    return httpx.Response(200, json={"job_id": "job_1", "state": "uploading", "upload": upload})


@pytest.mark.parametrize(("part", "total"), [(3000, 7), (3000, 2)])
def test_a_plan_that_does_not_describe_the_file_is_bad_part_plan(
    monkeypatch: pytest.MonkeyPatch, part: int, total: int
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: _plan(part, total)))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert raised.value.code == "bad_part_plan"
    assert raised.value.resume_token


@pytest.mark.parametrize(
    ("part", "total"),
    [
        (0, 3),
        (3000, 0),
        (-1, 3),
        (3000, -4),
        (1.5, 3),
        (3000, 2.0),
        ("3000", 2),
        (True, 2),
        (MAX_PART_BYTES + 1, 1),
    ],
)
def test_a_plan_with_a_number_that_cannot_be_one_is_bad_response_with_the_key(
    monkeypatch: pytest.MonkeyPatch, part: object, total: object
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: _plan(part, total)))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        200,
        None,
    )
    assert raised.value.idempotency_key


def test_a_part_url_page_with_a_non_positive_size_is_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=40)
    page: dict[str, object] = {
        "part_size_bytes": 0,
        "total_parts": 40,
        "part_urls": [],
        "next_part_number": None,
    }
    api.overrides.append(
        ("GET", r"/v1/uploads/[^/]+/part-urls", lambda: httpx.Response(200, json=page))
    )
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "bad_response"


def test_a_part_without_a_url_is_part_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(parts=40)
    page: dict[str, object] = {
        "part_size_bytes": 100,
        "total_parts": 40,
        "part_urls": [],
        "next_part_number": None,
    }
    api.overrides.append(
        ("GET", r"/v1/uploads/[^/]+/part-urls", lambda: httpx.Response(200, json=page))
    )
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "part_url_missing"


def test_a_stored_part_without_an_etag_is_etag_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(200) if n == 2 else None)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "etag_missing"
    assert api.r2_calls[2] == 1
    assert api.count("POST", COMPLETE) == 0


async def test_async_a_stored_part_without_an_etag_is_etag_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(200) if n == 2 else None)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "etag_missing"


# --- idempotency keys: 16 to 128 bytes of 0x21 to 0x7E ---


@pytest.mark.parametrize(
    "key", ["has a space in it!!", "x" * 15, "x" * 129, "café" * 5, "tab\there" * 3, "a" * 15 + " "]
)
def test_a_key_outside_the_server_rule_is_invalid_with_no_request(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    with pytest.raises(PreflightError) as raised:
        hs.transcribe(media(), duration_seconds=100, idempotency_key=key)
    assert raised.value.code == "invalid_option"
    assert api.requests == []


@pytest.mark.parametrize("key", ["!" * 16, "~" * 128, "k" * 36, "a-b_c.d:e/f=g+h"[:15] + "~"])
def test_a_key_inside_the_server_rule_is_sent_as_given(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    api = FakeApi()
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, idempotency_key=key)
    assert (
        httpx.Response(200, content=api.of("POST", CREATE)[0].content).json()["idempotency_key"]
        == key
    )


# --- pacing belongs to every POST /v1/uploads, keyed or not (spec 7.5) ---


def test_a_create_through_the_low_level_client_is_paced_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: httpx.Response(200, json={"job_id": "j"})))
    hs = hs_for(monkeypatch, api)
    clock = hs._clock
    client = hs.api.get_httpx_client()
    for _ in range(4):
        client.post(CREATE, json={})
    assert clock.now() == 0.0
    client.post(CREATE, json={})
    assert clock.now() >= 60.0
    assert api.count("POST", CREATE) == 5


async def test_async_a_keyless_create_is_paced(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: httpx.Response(200, json={"job_id": "j"})))
    hs = async_hs_for(monkeypatch, api)
    client = hs.api.get_async_httpx_client()
    for _ in range(5):
        await client.post(CREATE, json={})
    assert hs._clock.now() >= 60.0


def test_the_pipeline_create_is_paced_once_not_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi()
    clock = PipeClock()
    hs = hs_for(monkeypatch, api, clock)
    for _ in range(4):
        hs.transcribe(media(), duration_seconds=100)
    assert all(seconds < 15.0 for seconds in clock.sleeps)


# --- progress: 0% once before the create and before a resume's replay ---


def test_zero_percent_is_reported_once_even_when_the_create_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(create_steps=[error_reply(429, "rate_limited", 5000)])
    hs = hs_for(monkeypatch, api)
    seen: list[tuple[Progress, int]] = []
    hs.transcribe(
        media(),
        duration_seconds=100,
        on_progress=lambda p: seen.append((p, api.count("POST", CREATE))),
    )
    zeros = [(p, n) for p, n in seen if isinstance(p, UploadingProgress) and p.percent == 0]
    assert len(zeros) == 1
    assert zeros[0][1] == 0


def test_a_resume_that_replays_the_create_reports_zero_percent_before_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(503) if n == 3 else None)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as failed:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    api.r2_hook = None
    seen: list[tuple[Progress, int]] = []
    hs.resume(
        failed.value.resume_token or "",
        media(),
        on_progress=lambda p: seen.append((p, api.count("POST", CREATE))),
    )
    first, creates_then = seen[0]
    assert first == UploadingProgress(0, 0, 9000)
    assert creates_then == 1
    assert api.count("POST", CREATE) == 2


# --- resume opens a path only once the job is known to be uploading (spec 7.3) ---


def _waiting_token(monkeypatch: pytest.MonkeyPatch, api: FakeApi) -> tuple[Hushscript, str]:
    hs = hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(WaitTimeoutError):
        hs.transcribe(media(), duration_seconds=100, wait_timeout=10, on_resume_token=tokens.append)
    return hs, tokens[0]


def test_resume_of_a_finished_job_never_opens_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs, token = _waiting_token(monkeypatch, api)
    api.processing_polls = 0
    assert hs.resume(token, tmp_path / "gone.mp3").id
    assert api.count("POST", CREATE) == 1


def test_resume_of_an_uploading_job_with_an_unreadable_path_is_file_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi(r2_hook=lambda n, _a: httpx.Response(503) if n == 3 else None)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as failed:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    with pytest.raises(PreflightError) as raised:
        hs.resume(failed.value.resume_token or "", tmp_path / "gone.mp3")
    assert raised.value.code == "file_unreadable"
    assert api.count("POST", CREATE) == 1


def test_a_path_of_another_size_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs, token = _waiting_token(monkeypatch, api)
    other = tmp_path / "other.mp3"
    other.write_bytes(media(9001))
    before = len(api.requests)
    with pytest.raises(ResumeMismatchError) as raised:
        hs.resume(token, other)
    assert raised.value.code == "resume_file_mismatch"
    assert len(api.requests) == before


async def test_async_resume_of_a_finished_job_never_opens_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    api = FakeApi(processing_polls=10_000)
    hs = async_hs_for(monkeypatch, api)
    tokens: list[str] = []
    with pytest.raises(WaitTimeoutError):
        await hs.transcribe(
            media(), duration_seconds=100, wait_timeout=10, on_resume_token=tokens.append
        )
    api.processing_polls = 0
    assert (await hs.resume(tokens[0], tmp_path / "gone.mp3")).id
    assert api.count("POST", CREATE) == 1


# --- direct versus proxied is decided once (spec 8.4) ---


def test_a_direct_success_before_the_switch_keeps_the_upload_direct() -> None:
    state = UploadState(Mode.UNDECIDED)
    assert state.record(1, "e1") is True
    action = state.decide(PartAttempts(), 500)
    assert action is Action.REFRESH
    assert state.mode is Mode.DIRECT
    assert state.parts_body() == {"parts": [{"n": 1, "etag": "e1"}]}


def test_a_switch_before_the_direct_success_makes_the_success_lose() -> None:
    state = UploadState(Mode.UNDECIDED)
    assert state.decide(PartAttempts(), 500) is Action.FALLBACK
    assert state.record(1, "e1") is False
    assert state.mode is Mode.PROXIED
    assert state.etags == {}
    assert state.parts_body() is None


def test_every_part_follows_a_switch_somebody_else_made() -> None:
    state = UploadState(Mode.UNDECIDED)
    assert state.decide(PartAttempts(), 500) is Action.FALLBACK
    assert state.decide(PartAttempts(), 403) is Action.FALLBACK
    assert state.decide(PartAttempts(rounds=1), 500) is Action.FALLBACK


@pytest.mark.parametrize("trial", range(200))
def test_a_direct_success_and_a_switch_never_both_win(trial: int) -> None:
    state = UploadState(Mode.UNDECIDED)
    start = threading.Barrier(2)
    results: dict[str, object] = {}

    def success() -> None:
        start.wait()
        results["recorded"] = state.record(1, "e")

    def failure() -> None:
        start.wait()
        results["action"] = state.decide(PartAttempts(), 500)

    threads = [threading.Thread(target=success), threading.Thread(target=failure)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    recorded, action = results["recorded"], results["action"]
    assert (recorded, action is Action.FALLBACK) in {(True, False), (False, True)}, trial
    assert state.mode is (Mode.DIRECT if recorded else Mode.PROXIED)
    assert bool(state.etags) is recorded


def test_the_losing_direct_part_is_sent_through_the_api_with_no_direct_part_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    switched = threading.Event()

    def r2(n: int, _attempt: int) -> httpx.Response | None:
        if n == 2:
            return httpx.Response(500)
        if n == 1:
            switched.wait(10)
        return None

    api = FakeApi(r2_hook=r2, part_hook=lambda _n, _a: switched.set())
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=2)
    assert api.r2_calls[1] == 1
    assert api.part_calls == {1: 1, 2: 1, 3: 1}
    assert api.of("POST", COMPLETE)[0].content == b""
    assert all(not direct for _, _, direct in api.jobs["job_1"].parts.values())


# --- R83: the part size ceiling ---

PLAN: dict[str, object] = {
    "part_size_bytes": 3000,
    "total_parts": 3,
    "part_urls": [],
    "next_part_number": None,
}


def test_a_part_size_of_exactly_32_mib_is_a_plan_and_one_byte_more_is_not() -> None:
    assert parse_plan({**PLAN, "part_size_bytes": MAX_PART_BYTES, "total_parts": 1}).part_size == (
        MAX_PART_BYTES
    )
    with pytest.raises(BadBodyError):
        parse_plan({**PLAN, "part_size_bytes": MAX_PART_BYTES + 1, "total_parts": 1})


def test_a_part_url_page_above_the_part_size_ceiling_is_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=40)
    page = {**PLAN, "part_size_bytes": MAX_PART_BYTES + 1, "total_parts": 40}
    api.overrides.append(
        ("GET", r"/v1/uploads/[^/]+/part-urls", lambda: httpx.Response(200, json=page))
    )
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "bad_response"


# --- R70: a null part_urls means direct upload is not available (spec 8.3, 8.4) ---

R2 = r"/__r2/[^/]+/\d+"
PARTS = r"/v1/uploads/[^/]+/parts/\d+"
PART_URLS = r"/v1/uploads/[^/]+/part-urls"


def _all_proxied(api: FakeApi, parts: int) -> None:
    assert api.count("PUT", R2) == 0
    assert api.count("PUT", PARTS) == parts
    assert api.of("POST", COMPLETE)[0].content == b""


@pytest.mark.parametrize(("parts", "size"), [(3, 9000), (40, 4000)], ids=["no-next", "next-part"])
def test_a_null_part_urls_on_the_create_answer_goes_proxied(
    monkeypatch: pytest.MonkeyPatch, parts: int, size: int
) -> None:
    api = FakeApi(parts=parts, null_part_urls="create")
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(size), duration_seconds=100, concurrency=1)
    _all_proxied(api, parts)
    assert api.count("GET", PART_URLS) == 0


@pytest.mark.parametrize(("parts", "size"), [(3, 9000), (40, 4000)], ids=["no-next", "next-part"])
async def test_async_a_null_part_urls_on_the_create_answer_goes_proxied(
    monkeypatch: pytest.MonkeyPatch, parts: int, size: int
) -> None:
    api = FakeApi(parts=parts, null_part_urls="create")
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(size), duration_seconds=100, concurrency=1)
    _all_proxied(api, parts)
    assert api.count("GET", PART_URLS) == 0


def test_a_null_part_urls_page_before_any_direct_success_goes_proxied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=3, null_part_urls="page")
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _all_proxied(api, 3)
    assert api.count("GET", PART_URLS) == 1


async def test_async_a_null_part_urls_page_before_any_direct_success_goes_proxied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=3, null_part_urls="page")
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _all_proxied(api, 3)
    assert api.count("GET", PART_URLS) == 1


def test_a_null_part_urls_page_after_a_direct_success_keeps_the_direct_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the other half of the Fallback rule; the switch itself is the tests above."""
    api = FakeApi(parts=40, null_part_urls="late-page")
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "part_url_missing"
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


async def test_async_a_null_part_urls_page_after_a_direct_success_keeps_the_direct_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=40, null_part_urls="late-page")
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "part_url_missing"
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


# --- spec 8.3: a part-urls page that answers HTTP 404 is read as a null page ---


def _page_404_api(*, parts: int, null_part_urls: str = "") -> FakeApi:
    api = FakeApi(parts=parts, null_part_urls=null_part_urls)
    api.overrides.append(("GET", PART_URLS, lambda: error_reply(404, "not_found", 4000)))
    return api


def _null_page() -> httpx.Response:
    return httpx.Response(200, json={**PLAN, "part_urls": None})


def _not_found_page() -> httpx.Response:
    return error_reply(404, "not_found", 4000)


def _expired_part_3(n: int, _attempt: int) -> httpx.Response | None:
    return httpx.Response(403) if n == 3 else None


def _refresh_api(page: Callable[[], httpx.Response], *, direct_before: bool) -> FakeApi:
    api = FakeApi(parts=3)
    api.overrides.append(("GET", PART_URLS, page))
    if direct_before:
        api.r2_hook = _expired_part_3
    else:
        api.url_ttl_expired = True
    return api


def _went_proxied_after_refresh(api: FakeApi) -> None:
    assert api.count("PUT", PARTS) == 3
    assert api.of("POST", COMPLETE)[0].content == b""
    assert api.count("GET", PART_URLS) == 1


def test_a_404_part_urls_page_before_any_direct_success_goes_proxied_without_a_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _page_404_api(parts=3, null_part_urls="page")
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _all_proxied(api, 3)
    assert api.count("GET", PART_URLS) == 1


async def test_async_a_404_part_urls_page_before_any_direct_success_goes_proxied_without_a_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _page_404_api(parts=3, null_part_urls="page")
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _all_proxied(api, 3)
    assert api.count("GET", PART_URLS) == 1


def test_a_404_next_part_urls_page_after_a_direct_success_ends_like_a_null_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _page_404_api(parts=40)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "part_url_missing"
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


async def test_async_a_404_next_part_urls_page_after_a_direct_success_ends_like_a_null_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _page_404_api(parts=40)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "part_url_missing"
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


PAGE_ANSWERS = [_null_page, _not_found_page]
PAGE_IDS = ["null", "404"]


@pytest.mark.parametrize("page", PAGE_ANSWERS, ids=PAGE_IDS)
def test_a_refresh_page_without_urls_before_a_direct_success_goes_proxied(
    monkeypatch: pytest.MonkeyPatch, page: Callable[[], httpx.Response]
) -> None:
    api = _refresh_api(page, direct_before=False)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _went_proxied_after_refresh(api)


@pytest.mark.parametrize("page", PAGE_ANSWERS, ids=PAGE_IDS)
async def test_async_a_refresh_page_without_urls_before_a_direct_success_goes_proxied(
    monkeypatch: pytest.MonkeyPatch, page: Callable[[], httpx.Response]
) -> None:
    api = _refresh_api(page, direct_before=False)
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    _went_proxied_after_refresh(api)


@pytest.mark.parametrize("page", PAGE_ANSWERS, ids=PAGE_IDS)
def test_a_refresh_page_without_urls_after_a_direct_success_ends_the_same_for_404_and_null(
    monkeypatch: pytest.MonkeyPatch, page: Callable[[], httpx.Response]
) -> None:
    api = _refresh_api(page, direct_before=True)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "parts_exhausted"
    assert api.count("GET", PART_URLS) == 2
    assert api.count("PUT", PARTS) == 0


@pytest.mark.parametrize("page", PAGE_ANSWERS, ids=PAGE_IDS)
async def test_async_a_refresh_page_without_urls_after_a_direct_success_ends_the_same(
    monkeypatch: pytest.MonkeyPatch, page: Callable[[], httpx.Response]
) -> None:
    api = _refresh_api(page, direct_before=True)
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "parts_exhausted"
    assert api.count("GET", PART_URLS) == 2
    assert api.count("PUT", PARTS) == 0


def test_a_404_from_a_proxied_part_keeps_its_meaning(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeApi(parts=3, null_part_urls="create")
    api.overrides.append(("PUT", PARTS, lambda: error_reply(404, "not_found", 4000)))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(NotFoundError):
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("GET", PART_URLS) == 0


async def test_async_a_404_from_a_proxied_part_keeps_its_meaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi(parts=3, null_part_urls="create")
    api.overrides.append(("PUT", PARTS, lambda: error_reply(404, "not_found", 4000)))
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(NotFoundError):
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert api.count("GET", PART_URLS) == 0


# --- R8: size_exceeded from part-urls ends the upload as itself ---


def _size_exceeded_api(*, parts: int, null_part_urls: str) -> FakeApi:
    api = FakeApi(parts=parts, null_part_urls=null_part_urls)
    api.overrides.append(
        ("GET", PART_URLS, lambda: error_reply(422, "size_exceeded", 1024)),
    )
    return api


def test_size_exceeded_from_part_urls_before_a_direct_success_ends_the_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _size_exceeded_api(parts=3, null_part_urls="page")
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "size_exceeded"
    assert raised.value.status == 422
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 0
    assert api.count("PUT", PARTS) == 0
    assert api.count("POST", COMPLETE) == 0


async def test_async_size_exceeded_from_part_urls_before_a_direct_success_ends_the_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _size_exceeded_api(parts=3, null_part_urls="page")
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "size_exceeded"
    assert raised.value.status == 422
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 0
    assert api.count("PUT", PARTS) == 0
    assert api.count("POST", COMPLETE) == 0


def test_size_exceeded_from_part_urls_after_a_direct_success_is_not_parts_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _size_exceeded_api(parts=40, null_part_urls="")
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "size_exceeded"
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


async def test_async_size_exceeded_from_part_urls_after_a_direct_success_is_not_parts_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _size_exceeded_api(parts=40, null_part_urls="")
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        await hs.transcribe(media(4000), duration_seconds=100, concurrency=1)
    assert raised.value.code == "size_exceeded"
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", R2) == 16
    assert api.count("PUT", PARTS) == 0


def test_size_exceeded_from_the_refresh_after_an_expired_url_ends_the_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _size_exceeded_api(parts=3, null_part_urls="")
    api.r2_hook = lambda _n, _attempt: httpx.Response(403)
    hs = hs_for(monkeypatch, api)
    with pytest.raises(UploadError) as raised:
        hs.transcribe(media(), duration_seconds=100, concurrency=1)
    assert raised.value.code == "size_exceeded"
    assert api.count("GET", PART_URLS) == 1
    assert api.count("PUT", PARTS) == 0


# --- ids from the server go into paths as one encoded segment ---


def _created(job_id: str) -> httpx.Response:
    body = json.dumps({"job_id": job_id, "state": "uploading", "upload": None})  # ASCII escapes
    return httpx.Response(200, content=body.encode(), headers=JSON)


UNUSABLE_IDS = ["", ".", "..", "a/b", "../x", "a\\b", "\ud800"]


@pytest.mark.parametrize("job_id", UNUSABLE_IDS)
def test_a_create_answer_with_an_unusable_job_id_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, job_id: str
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: _created(job_id)))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert raised.value.idempotency_key
    assert all(request.url.path in {"/v1/account", CREATE} for request in api.requests)


@pytest.mark.parametrize("job_id", UNUSABLE_IDS)
async def test_async_a_create_answer_with_an_unusable_job_id_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, job_id: str
) -> None:
    api = FakeApi()
    api.overrides.append(("POST", CREATE, lambda: _created(job_id)))
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        await hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert all(request.url.path in {"/v1/account", CREATE} for request in api.requests)


def _raw_paths(api: FakeApi, prefix: str) -> list[str]:
    return [
        request.url.raw_path.decode().split("?")[0]
        for request in api.requests
        if request.url.raw_path.decode().startswith(prefix)
    ]


AWKWARD = "j #?%é-"


@pytest.mark.parametrize("proxied", [False, True])
def test_a_job_id_is_percent_encoded_in_every_path(
    monkeypatch: pytest.MonkeyPatch,
    proxied: bool,  # noqa: FBT001
) -> None:
    api = FakeApi(job_prefix=AWKWARD, proxied=proxied)
    hs = hs_for(monkeypatch, api)
    hs.transcribe(media(), duration_seconds=100)
    encoded = quote(f"{AWKWARD}1", safe="")
    paths = _raw_paths(api, "/v1/uploads/") + _raw_paths(api, "/v1/jobs/")
    assert len(paths) >= 3
    assert all(f"/{encoded}" in path and "/ " not in path for path in paths), paths


@pytest.mark.parametrize("proxied", [False, True])
async def test_async_a_job_id_is_percent_encoded_in_every_path(
    monkeypatch: pytest.MonkeyPatch,
    proxied: bool,  # noqa: FBT001
) -> None:
    api = FakeApi(job_prefix=AWKWARD, proxied=proxied)
    hs = async_hs_for(monkeypatch, api)
    await hs.transcribe(media(), duration_seconds=100)
    encoded = quote(f"{AWKWARD}1", safe="")
    paths = _raw_paths(api, "/v1/uploads/") + _raw_paths(api, "/v1/jobs/")
    assert len(paths) >= 3
    assert all(f"/{encoded}" in path for path in paths), paths


def _done_job_with(transcript_id: str) -> httpx.Response:
    job: dict[str, object] = {
        "id": "job_1",
        "state": "done",
        "mode": "standard",
        "declared_seconds": 24,
        "verified_seconds": None,
        "actual_seconds": None,
        "billable_seconds": 0,
        "retry_of": None,
        "created_at": 1_700_000_000,
        "options": {},
        "transcript_id": transcript_id,
        "error": None,
        "failure_kind": None,
    }
    return httpx.Response(200, json=job)


@pytest.mark.parametrize("transcript_id", ["..", "a/b"])
def test_a_job_naming_an_unusable_transcript_id_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, transcript_id: str
) -> None:
    api = FakeApi()
    api.overrides.append(("GET", r"/v1/jobs/[^/]+", lambda: _done_job_with(transcript_id)))
    hs = hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert api.count("GET", r"/v1/transcripts/.*") == 0


@pytest.mark.parametrize("transcript_id", ["..", "a/b"])
async def test_async_a_job_naming_an_unusable_transcript_id_is_bad_response(
    monkeypatch: pytest.MonkeyPatch, transcript_id: str
) -> None:
    api = FakeApi()
    api.overrides.append(("GET", r"/v1/jobs/[^/]+", lambda: _done_job_with(transcript_id)))
    hs = async_hs_for(monkeypatch, api)
    with pytest.raises(ApiError) as raised:
        await hs.transcribe(media(), duration_seconds=100)
    assert (raised.value.code, raised.value.status) == ("bad_response", 200)
    assert api.count("GET", r"/v1/transcripts/.*") == 0
