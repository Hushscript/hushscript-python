# pyright: reportPrivateUsage=false
from __future__ import annotations

import pytest

from helpers import FakeClock, job_body
from hushscript import JobFailedError, ProcessingProgress, UploadError, WaitTimeoutError
from hushscript._models import Job, Progress
from hushscript._response import BadBodyError
from hushscript.transcribe.wait import (
    await_job,
    finish,
    next_delay,
    wait_for_job,
)


def _job(state: str, **fields: object) -> Job:
    return Job.from_body(job_body("job_1", state, **fields))


def _flow(*states: str) -> list[Job]:
    return [_job(state) for state in states]


def test_the_poll_delay_grows_by_half_to_fifteen_seconds() -> None:
    delays = [5.0]
    for _ in range(5):
        delays.append(next_delay(delays[-1]))
    assert delays == [5.0, 7.5, 11.25, 15.0, 15.0, 15.0]


def test_a_job_is_polled_on_the_documented_cadence_until_it_is_done() -> None:
    clock = FakeClock()
    jobs = _flow("queued", "processing", "processing", "processing", "processing", "done")
    seen: list[Progress] = []
    result = wait_for_job(lambda: jobs.pop(0), clock, 3600, seen.append)
    assert result.state == "done"
    assert clock.sleeps == [5.0, 7.5, 11.25, 15.0, 15.0]
    assert seen[0] == ProcessingProgress(state="queued")
    assert len(seen) == 5


def test_a_job_that_is_done_at_once_is_read_once_and_never_slept_on() -> None:
    clock = FakeClock()
    result = wait_for_job(lambda: _job("done"), clock, 3600)
    assert result.state == "done"
    assert clock.sleeps == []


def test_a_failed_job_is_returned_for_the_caller_to_judge() -> None:
    assert wait_for_job(lambda: _job("failed"), FakeClock(), 60).state == "failed"


def test_an_unknown_state_keeps_the_polling_going() -> None:
    clock = FakeClock()
    jobs = _flow("reticulating", "done")
    assert wait_for_job(lambda: jobs.pop(0), clock, 60).state == "done"
    assert clock.sleeps == [5.0]


def test_the_wait_ends_at_the_timeout_with_a_last_poll_and_the_token() -> None:
    clock = FakeClock()
    polls: list[float] = []

    def get() -> Job:
        polls.append(clock.now())
        return _job("processing")

    with pytest.raises(WaitTimeoutError) as raised:
        wait_for_job(get, clock, 60, token="tok")
    assert raised.value.resume_token == "tok"
    assert polls[-1] == 60
    assert sum(clock.sleeps) == 60
    assert raised.value.code == "wait_timeout"


def test_finish_gives_the_transcript_id_of_a_done_job() -> None:
    assert finish(_job("done", transcript_id="tr_1")) == "tr_1"


def test_a_failed_job_raises_with_what_the_api_said() -> None:
    job = _job("failed", error="Could not decode", failure_kind="media_undecodable")
    with pytest.raises(JobFailedError) as raised:
        finish(job)
    assert (raised.value.job_id, raised.value.error, raised.value.failure_kind) == (
        "job_1",
        "Could not decode",
        "media_undecodable",
    )


def test_a_done_job_without_a_transcript_id_is_an_upload_error() -> None:
    with pytest.raises(UploadError) as raised:
        finish(_job("done"))
    assert raised.value.code == "transcript_missing"


def test_a_job_body_without_an_id_is_refused() -> None:
    with pytest.raises(BadBodyError, match="id: expected a value"):
        Job.from_body({k: v for k, v in job_body("job_1", "done").items() if k != "id"})
    with pytest.raises(BadBodyError, match="expected an object"):
        Job.from_body([])


@pytest.mark.anyio
async def test_the_async_wait_polls_on_the_same_cadence() -> None:
    clock = FakeClock()
    jobs = _flow("queued", "processing", "done")

    async def get() -> Job:
        return jobs.pop(0)

    seen: list[Progress] = []
    result = await await_job(get, clock, 3600, seen.append)
    assert result.state == "done"
    assert clock.sleeps == [5.0, 7.5]
    assert len(seen) == 2


@pytest.mark.anyio
async def test_the_async_wait_times_out_with_the_token() -> None:
    clock = FakeClock()

    async def get() -> Job:
        return _job("processing")

    with pytest.raises(WaitTimeoutError) as raised:
        await await_job(get, clock, 20, token="tok")
    assert raised.value.resume_token == "tok"
    assert sum(clock.sleeps) == 20
